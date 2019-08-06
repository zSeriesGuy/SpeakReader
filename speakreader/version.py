#  This file is part of SpeakReader.

import os
import platform
import re
import subprocess
import tarfile
import json

import speakreader
from speakreader import logger
import requests


initial_hash = "4e91264061f008fa14787b325c178efdefd3b11c"
current_hash = "56b3d03616c9e51240f1efc8735acfef04bc1319"


class Version(object):
    INSTALL_TYPE = None
    INSTALLED_VERSION_HASH = None
    INSTALLED_RELEASE = None
    LATEST_VERSION_HASH = None
    LATEST_RELEASE = None
    COMMITS_BEHIND = None
    UPDATE_AVAILABLE = False
    REMOTE_NAME = None
    BRANCH_NAME = None

    def __init__(self):
        self.INSTALLED_RELEASE = speakreader.VERSION_RELEASE
        self.LATEST_RELEASE = speakreader.VERSION_RELEASE

        if os.path.isdir(os.path.join(speakreader.PROG_DIR, '.git')):
            self.INSTALL_TYPE = 'git'

            output, err = runGit('rev-parse HEAD')
            if output:
                if re.match('^[a-z0-9]+$', output):
                    self.INSTALLED_VERSION_HASH = output
                else:
                    logger.error('Output does not look like a hash, not using it.')
            else:
                logger.error('Could not find latest installed version.')

            if speakreader.CONFIG.DO_NOT_OVERRIDE_GIT_BRANCH and speakreader.CONFIG.GIT_BRANCH:
                self.BRANCH_NAME = speakreader.CONFIG.GIT_BRANCH
            else:
                remote_branch, err = runGit('rev-parse --abbrev-ref --symbolic-full-name @{u}')
                remote_branch = remote_branch.rsplit('/', 1) if remote_branch else []
                if len(remote_branch) == 2:
                    self.REMOTE_NAME, self.BRANCH_NAME = remote_branch

                if not self.REMOTE_NAME and speakreader.CONFIG.GIT_REMOTE:
                    logger.error('Could not retrieve remote name from git. Falling back to %s.' % speakreader.CONFIG.GIT_REMOTE)
                    self.REMOTE_NAME = speakreader.CONFIG.GIT_REMOTE

                if not self.REMOTE_NAME:
                    logger.error('Could not retrieve remote name from git. Defaulting to origin.')
                    self.REMOTE_NAME = 'origin'

                if not self.BRANCH_NAME and speakreader.CONFIG.GIT_BRANCH:
                    logger.error('Could not retrieve branch name from git. Falling back to %s.' % speakreader.CONFIG.GIT_BRANCH)
                    self.BRANCH_NAME = speakreader.CONFIG.GIT_BRANCH

                if not self.BRANCH_NAME:
                    logger.error('Could not retrieve branch name from git. Defaulting to master.')
                    self.BRANCH_NAME = 'master'

        else:
            self.INSTALL_TYPE = 'source'
            self.REMOTE_NAME = 'origin'
            self.BRANCH_NAME = speakreader.GITHUB_BRANCH

            version_file = os.path.join(speakreader.PROG_DIR, 'version.txt')
            if os.path.isfile(version_file):
                with open(version_file, 'r') as f:
                    self.INSTALLED_VERSION_HASH = f.read().strip(' \n\r')


        # Check for new versions
        if speakreader.CONFIG.CHECK_GITHUB:
            self.INSTALLED_VERSION_HASH = initial_hash
            self.check_github()
        else:
            self.LATEST_VERSION_HASH = self.INSTALLED_VERSION_HASH

        if not self.INSTALLED_VERSION_HASH:
            self.UPDATE_AVAILABLE = None
        elif self.COMMITS_BEHIND > 0 and speakreader.GITHUB_BRANCH in ('master', 'beta') and \
                speakreader.VERSION_RELEASE != self.LATEST_RELEASE:
            self.UPDATE_AVAILABLE = 'release'
        elif self.COMMITS_BEHIND > 0 and self.INSTALLED_VERSION_HASH != self.LATEST_VERSION_HASH:
            self.UPDATE_AVAILABLE = 'commit'
        else:
            self.UPDATE_AVAILABLE = False


    def check_github(self):

        self.COMMITS_BEHIND = 0

        # Get the latest version available from github
        logger.info('Retrieving latest version information from GitHub')
        url = 'https://api.github.com/repos/%s/%s/commits/%s' % (speakreader.CONFIG.GIT_USER,
                                                                 speakreader.CONFIG.GIT_REPO,
                                                                 speakreader.CONFIG.GIT_BRANCH)
        if speakreader.CONFIG.GIT_TOKEN: url = url + '?access_token=%s' % speakreader.CONFIG.GIT_TOKEN
        response = requests.get(url, timeout=20)

        if response.ok:
            version = response.json()
        else:
            logger.warn('Could not get the latest version from GitHub. Are you running a local development version?')
            return

        self.LATEST_VERSION_HASH = version['sha']
        logger.debug("Latest version is %s", self.LATEST_VERSION_HASH)

        # See how many commits behind we are
        if not self.INSTALLED_VERSION_HASH:
            logger.info('You are running an unknown version of SpeakReader. Run the updater to identify your version')
            return

        if self.LATEST_VERSION_HASH == self.INSTALLED_VERSION_HASH:
            logger.info('SpeakReader is up to date')
            return

        logger.info('Comparing currently installed version with latest GitHub version')
        url = 'https://api.github.com/repos/%s/%s/compare/%s...%s' % (speakreader.CONFIG.GIT_USER,
                                                                      speakreader.CONFIG.GIT_REPO,
                                                                      self.LATEST_VERSION_HASH,
                                                                      self.INSTALLED_VERSION_HASH)
        if speakreader.CONFIG.GIT_TOKEN: url = url + '?access_token=%s' % speakreader.CONFIG.GIT_TOKEN
        response = requests.get(url, timeout=20)

        if response.ok:
            commits = response.json()
        else:
            logger.warn('Could not get commits behind from GitHub.')
            return

        try:
            self.COMMITS_BEHIND = int(commits['behind_by'])
            logger.debug("In total, %d commits behind", self.COMMITS_BEHIND)
        except KeyError:
            logger.info('Cannot compare versions. Are you running a local development version?')
            self.COMMITS_BEHIND = 0

        if self.COMMITS_BEHIND > 0:
            logger.info('New version is available. You are %s commits behind' % self.COMMITS_BEHIND)

            url = 'https://api.github.com/repos/%s/%s/releases' % (speakreader.CONFIG.GIT_USER, speakreader.CONFIG.GIT_REPO)
            response = requests.get(url, timeout=20)

            if response.ok:
                releases = response.json()
            else:
                logger.warn('Could not get releases from GitHub.')
                return

            if speakreader.CONFIG.GIT_BRANCH == 'master':
                release = next((r for r in releases if not r['prerelease']), releases[0])
            elif speakreader.CONFIG.GIT_BRANCH == 'beta':
                release = next((r for r in releases if not r['tag_name'].endswith('-nightly')), releases[0])
            elif speakreader.CONFIG.GIT_BRANCH == 'nightly':
                release = next((r for r in releases), releases[0])
            else:
                release = releases[0]

            self.LATEST_RELEASE = release['tag_name']

        elif self.COMMITS_BEHIND == 0:
            logger.info('SpeakReader is up to date')


def runGit(args):
    if speakreader.CONFIG.GIT_PATH:
        git_locations = ['"' + speakreader.CONFIG.GIT_PATH + '"']
    else:
        git_locations = ['git']

    output = err = None

    for cur_git in git_locations:
        cmd = cur_git + ' ' + args

        try:
            logger.debug('Trying to execute: "' + cmd + '" with shell in ' + speakreader.PROG_DIR)
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True,
                                 cwd=speakreader.PROG_DIR)
            output, err = p.communicate()
            output = output.strip().decode('utf-8')

            logger.debug('Git output: ' + output)
        except OSError:
            logger.debug('Command failed: %s', cmd)
            continue

        if 'not found' in output or "not recognized as an internal or external command" in output:
            logger.debug('Unable to find git with command ' + cmd)
            output = None
        elif 'fatal:' in output or err:
            logger.error('Git returned bad info. Are you sure this is a git installation?')
            output = None
        elif output:
            break

    return (output, err)

