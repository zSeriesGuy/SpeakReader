# **************************************************************************************
# * This file is part of SpeakReader.
# *
# *  SpeakReader is free software: you can redistribute it and/or modify
# *  it under the terms of the GNU General Public License V3 as published by
# *  the Free Software Foundation.
# *
# *  SpeakReader is distributed in the hope that it will be useful,
# *  but WITHOUT ANY WARRANTY; without even the implied warranty of
# *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# *  GNU General Public License for more details.
# *
# *  You should have received a copy of the GNU General Public License
# *  along with SpeakReader.  If not, see <http://www.gnu.org/licenses/gpl-3.0.html>.
# **************************************************************************************

#  This modules handles product updates.

import os
import re
import subprocess
import tarfile

import speakreader
from speakreader import logger
import requests


class Version(object):

    def __init__(self):

        self.INSTALL_TYPE = None
        self.INSTALLED_VERSION_HASH = None
        self.INSTALLED_RELEASE = speakreader.VERSION_RELEASE
        self.LATEST_VERSION_HASH = None
        self.LATEST_RELEASE = "Unknown"
        self.LATEST_RELEASE_URL = ""
        self.COMMITS_BEHIND = 0
        self.UPDATE_AVAILABLE = False
        self.REMOTE_NAME = None
        self.BRANCH_NAME = None
        self.version_lock_file = os.path.join(speakreader.DATA_DIR, "version.lock")
        self.release_lock_file = os.path.join(speakreader.DATA_DIR, "release.lock")

        installed_release = self.getReleaseLock()
        if self.INSTALLED_RELEASE != installed_release:
            self.setReleaseLock(self.INSTALLED_RELEASE)

        if os.path.isdir(os.path.join(speakreader.PROG_DIR, '.git')):
            self.INSTALL_TYPE = 'git'

            output, err = runGit('rev-parse HEAD')
            if output:
                if re.match('^[a-z0-9]+$', output):
                    self.INSTALLED_VERSION_HASH = output
                    installed_version_hash = self.getVersionLock()
                    if self.INSTALLED_VERSION_HASH != installed_version_hash:
                        self.setVersionLock(self.INSTALLED_VERSION_HASH)
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
            self.INSTALLED_VERSION_HASH = self.getVersionLock()

        if speakreader.CONFIG.CHECK_GITHUB:
            self.checkForUpdate()

    def getVersionLock(self):
        # Get the previous version from the file
        version_hash = "unknown"
        if os.path.isfile(self.version_lock_file):
            try:
                with open(self.version_lock_file, "r") as fp:
                    version_hash = fp.read()
            except IOError as e:
                logger.error("Unable to read previous version from file '%s': %s" %
                             (self.version_lock_file, e))
        return version_hash


    def setVersionLock(self, version_hash):
        # Set the previous version in the lock file
        try:
            with open(self.version_lock_file, "w") as fp:
                fp.write(version_hash)
        except IOError as e:
            logger.error(u"Unable to write current version to file '%s': %s" %
                         (self.version_lock_file, e))


    def getReleaseLock(self):
        # Get the previous release from the lock file
        release = False
        if os.path.isfile(self.release_lock_file):
            try:
                with open(self.release_lock_file, "r") as fp:
                    release = fp.read()
            except IOError as e:
                logger.error("Unable to read previous release from file '%s': %s" %
                             (self.release_lock_file, e))
        return release


    def setReleaseLock(self, release):
        # Set the previous release in the lock file
        try:
            with open(self.release_lock_file, "w") as fp:
                fp.write(release)
        except IOError as e:
            logger.error(u"Unable to write current version to file '%s': %s" %
                         (self.release_lock_file, e))


    def checkForUpdate(self):
        # Check for new versions
        if speakreader.CONFIG.CHECK_GITHUB:
            self._check_github()
        else:
            self.LATEST_VERSION_HASH = self.INSTALLED_VERSION_HASH

        if not self.INSTALLED_VERSION_HASH:
            self.UPDATE_AVAILABLE = True
        elif self.COMMITS_BEHIND > 0 and speakreader.GITHUB_BRANCH in ('master', 'beta') and \
                speakreader.VERSION_RELEASE != self.LATEST_RELEASE:
            self.UPDATE_AVAILABLE = 'release'
        elif self.COMMITS_BEHIND > 0 and self.INSTALLED_VERSION_HASH != self.LATEST_VERSION_HASH:
            self.UPDATE_AVAILABLE = 'commit'
        else:
            self.UPDATE_AVAILABLE = False

        if logger.VERBOSE:
            d = self.__dict__
            for k, v in d.items():
                logger.debug(str(k) + ": " + str(v))


    def _check_github(self):

        self.COMMITS_BEHIND = 0

        # Get the latest version available from github
        logger.debug('Retrieving latest version information from GitHub')
        url = 'https://api.github.com/repos/%s/%s/commits/%s' % (speakreader.CONFIG.GIT_USER,
                                                                 speakreader.CONFIG.GIT_REPO,
                                                                 speakreader.CONFIG.GIT_BRANCH)
        if speakreader.CONFIG.GIT_TOKEN: url = url + '?access_token=%s' % speakreader.CONFIG.GIT_TOKEN
        try:
            response = requests.get(url, timeout=10)
        except Exception as e:
            logger.warn('Failed to establish a connection to GitHub')
            return

        if response.ok:
            version = response.json()
        else:
            logger.warn('Could not get the latest version information from GitHub for ' + speakreader.CONFIG.GIT_REMOTE + '/' + speakreader.CONFIG.GIT_BRANCH + '. Are you running a local development version?')
            return

        self.LATEST_VERSION_HASH = version['sha']

        # See how many commits behind we are
        if not self.INSTALLED_VERSION_HASH:
            logger.info('You are running an unknown version of SpeakReader. Run the updater to identify your version')
            self.LATEST_RELEASE = "Unknown"
            return

        # Get latest release tag
        logger.debug('Retrieving latest release information from GitHub')
        url = 'https://api.github.com/repos/%s/%s/releases' % (speakreader.CONFIG.GIT_USER, speakreader.CONFIG.GIT_REPO)
        if speakreader.CONFIG.GIT_TOKEN: url = url + '?access_token=%s' % speakreader.CONFIG.GIT_TOKEN
        try:
            response = requests.get(url, timeout=10)
        except Exception as e:
            logger.warn('Failed to establish a connection to GitHub')
            return

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
        url = 'https://github.com/%s/%s/releases/tag/%s' \
              % (speakreader.CONFIG.GIT_USER, speakreader.CONFIG.GIT_REPO, self.LATEST_RELEASE)
        if speakreader.CONFIG.GIT_TOKEN: url = url + '?access_token=%s' % speakreader.CONFIG.GIT_TOKEN
        self.LATEST_RELEASE_URL = url

        logger.info("Installed release is %s - %s" % (self.INSTALLED_RELEASE, self.INSTALLED_VERSION_HASH))
        logger.info("Latest release is %s - %s" % (self.LATEST_RELEASE, self.LATEST_VERSION_HASH))

        if self.LATEST_VERSION_HASH == self.INSTALLED_VERSION_HASH:
            logger.info('SpeakReader is up to date')
            return

        logger.debug('Comparing currently installed version with latest GitHub version')
        url = 'https://api.github.com/repos/%s/%s/compare/%s...%s' % (speakreader.CONFIG.GIT_USER,
                                                                      speakreader.CONFIG.GIT_REPO,
                                                                      self.LATEST_VERSION_HASH,
                                                                      self.INSTALLED_VERSION_HASH)
        if speakreader.CONFIG.GIT_TOKEN: url = url + '?access_token=%s' % speakreader.CONFIG.GIT_TOKEN
        try:
            response = requests.get(url, timeout=10)
        except Exception as e:
            logger.warn('Failed to establish a connection to GitHub')
            return

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
        elif self.COMMITS_BEHIND == 0:
            logger.info('SpeakReader is up to date')


    def update(self):
        if speakreader.CONFIG.SERVER_ENVIRONMENT != 'production':
            logger.info("Updating bypassed because this is not a production environment")
            return False

        if not self.UPDATE_AVAILABLE:
            logger.info("No Updates Available")
            return False

        if self.INSTALL_TYPE == 'git':
            os.remove(os.path.join(speakreader.DATA_DIR, 'requirements.txt'))
            output, err = runGit('pull ' + speakreader.CONFIG.GIT_REMOTE + ' ' + speakreader.CONFIG.GIT_BRANCH)

            if not output:
                logger.error('Unable to download latest version')
                return False

            for line in output.split('\n'):
                if 'Already up-to-date.' in line:
                    logger.info('No update available, not updating')
                    logger.info('Output: ' + str(output))
                    return False
                elif line.endswith(('Aborting', 'Aborting.')):
                    logger.error('Unable to update from git: ' + line)
                    logger.info('Output: ' + str(output))
                    return False

        else:
            tar_download_url = 'https://api.github.com/repos/{}/{}/tarball/{}'.format(speakreader.CONFIG.GIT_USER, speakreader.CONFIG.GIT_REPO, speakreader.CONFIG.GIT_BRANCH)
            if speakreader.CONFIG.GIT_TOKEN: tar_download_url = tar_download_url + '?access_token=%s' % speakreader.CONFIG.GIT_TOKEN
            update_dir = os.path.join(speakreader.PROG_DIR, 'update')
            version_path = os.path.join(speakreader.PROG_DIR, 'version.txt')

            logger.info('Downloading update from: ' + tar_download_url)
            try:
                data = requests.get(tar_download_url, timeout=10)
            except Exception as e:
                logger.warn('Failed to establish a connection to GitHub')
                return False

            if not data:
                logger.error("Unable to retrieve new version from '%s', can't update", tar_download_url)
                return False

            download_name = speakreader.CONFIG.GIT_BRANCH + '-github'
            tar_download_path = os.path.join(speakreader.PROG_DIR, download_name)

            # Save tar to disk
            with open(tar_download_path, 'wb') as f:
                f.write(data.content)

            # Extract the tar to update folder
            logger.info('Extracting file: ' + tar_download_path)
            tar = tarfile.open(tar_download_path)
            tar.extractall(update_dir)
            tar.close()

            # Delete the tar.gz
            logger.info('Deleting file: ' + tar_download_path)
            os.remove(tar_download_path)

            # Find update dir name
            update_dir_contents = [x for x in os.listdir(update_dir) if os.path.isdir(os.path.join(update_dir, x))]
            if len(update_dir_contents) != 1:
                logger.error("Invalid update data, update failed: " + str(update_dir_contents))
                return False
            content_dir = os.path.join(update_dir, update_dir_contents[0])

            # walk temp folder and move files to main folder
            for dirname, dirnames, filenames in os.walk(content_dir):
                dirname = dirname[len(content_dir) + 1:]
                for curfile in filenames:
                    old_path = os.path.join(content_dir, dirname, curfile)
                    new_path = os.path.join(speakreader.PROG_DIR, dirname, curfile)

                    if os.path.isfile(new_path):
                        os.remove(new_path)
                    os.renames(old_path, new_path)

            # Update version.txt
            try:
                with open(version_path, 'w') as f:
                    f.write(str(self.LATEST_VERSION_HASH))
            except IOError as e:
                logger.error(
                    "Unable to write current version to version.txt, update not complete: %s",
                    e
                )
                return False

        logger.info("Update Completed Successfully")
        return True

    def checkout_git_branch(self):
        if self.INSTALL_TYPE == 'git':
            output, err = runGit('fetch %s' % speakreader.CONFIG.GIT_REMOTE)
            output, err = runGit('checkout %s' % speakreader.CONFIG.GIT_BRANCH)

            if not output:
                logger.error('Unable to change git branch.')
                return

            for line in output.split('\n'):
                if line.endswith(('Aborting', 'Aborting.')):
                    logger.error('Unable to checkout from git: ' + line)
                    logger.info('Output: ' + str(output))

            output, err = runGit('pull %s %s' % (speakreader.CONFIG.GIT_REMOTE, speakreader.CONFIG.GIT_BRANCH))


    def read_changelog(self, latest_only=False, since_prev_release=False):
        changelog_file = os.path.join(speakreader.PROG_DIR, 'CHANGELOG.md')

        if not os.path.isfile(changelog_file):
            return '<h4>Missing changelog file</h4>'

        try:
            output = ['']
            prev_level = 0

            latest_version_found = False

            header_pattern = re.compile(r'(^#+)\s(.+)')
            list_pattern = re.compile(r'(^[ \t]*\*\s)(.+)')

            with open(changelog_file, "r") as logfile:
                for line in logfile:
                    line_header_match = re.search(header_pattern, line)
                    line_list_match = re.search(list_pattern, line)

                    if line_header_match:
                        header_level = str(len(line_header_match.group(1)))
                        header_text = line_header_match.group(2)

                        if header_text.lower() == 'changelog':
                            continue

                        if latest_version_found:
                            break
                        elif latest_only:
                            latest_version_found = True
                        # Add a space to the end of the release to match tags
                        elif since_prev_release and str(self.INSTALLED_RELEASE) + ' ' in header_text:
                            break

                        output[-1] += '<h' + header_level + '>' + header_text + '</h' + header_level + '>'

                    elif line_list_match:
                        line_level = len(line_list_match.group(1)) / 2
                        line_text = line_list_match.group(2)

                        if line_level > prev_level:
                            output[-1] += '<ul>' * int(line_level - prev_level) + '<li>' + line_text + '</li>'
                        elif line_level < prev_level:
                            output[-1] += '</ul>' * int(prev_level - line_level) + '<li>' + line_text + '</li>'
                        else:
                            output[-1] += '<li>' + line_text + '</li>'

                        prev_level = line_level

                    elif line.strip() == '' and prev_level:
                        output[-1] += '</ul>' * int(prev_level)
                        output.append('')
                        prev_level = 0

            if since_prev_release:
                output.reverse()

            return ''.join(output)

        except IOError as e:
            logger.error('Unable to open changelog file. %s' % e)
            return '<h4>Unable to open changelog file</h4>'


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

