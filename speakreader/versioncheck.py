#  This file is part of Tautulli.
#
#  Tautulli is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Tautulli is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Tautulli.  If not, see <http://www.gnu.org/licenses/>.

import os
import platform
import re
import subprocess
import tarfile
import json

import speakreader
from speakreader import logger
import requests

INSTALL_TYPE = None
INSTALLED_VERSION_HASH = None
INSTALLED_RELEASE = None
LATEST_VERSION_HASH = None
COMMITS_BEHIND = None
LATEST_RELEASE = None
UPDATE_AVAILABLE = False


def version_init():

    global INSTALL_TYPE
    global INSTALLED_VERSION_HASH
    global INSTALLED_RELEASE
    global LATEST_VERSION_HASH
    global COMMITS_BEHIND
    global INSTALLED_RELEASE
    global LATEST_RELEASE
    global UPDATE_AVAILABLE
    
    # Get the previous version from the version lock file
    version_lock_file = os.path.join(speakreader.DATA_DIR, "version.lock")
    release_lock_file = os.path.join(speakreader.DATA_DIR, "release.lock")

    # Get the currently installed version. Returns None, 'win32' or the git hash.
    INSTALL_TYPE, INSTALLED_VERSION_HASH, speakreader.CONFIG.GIT_REMOTE, speakreader.CONFIG.GIT_BRANCH = getInstalledVersion()
    INSTALLED_RELEASE = speakreader.RELEASE

    # Get the previous version hash from the file
    prev_version_hash = None
    if os.path.isfile(version_lock_file):
        try:
            with open(version_lock_file, "r") as fp:
                prev_version_hash = fp.read()
        except IOError as e:
            logger.error("Unable to read previous version from file '%s': %s" %
                         (version_lock_file, e))
            if INSTALLED_VERSION_HASH:
                try:
                    with open(version_lock_file, "w") as fp:
                        fp.write(INSTALLED_VERSION_HASH)
                except IOError as e:
                    logger.error("Unable to write current version to file '%s': %s" %
                                 (version_lock_file, e))

    # Get the previous release from the file
    if os.path.isfile(release_lock_file):
        try:
            with open(release_lock_file, "r") as fp:
                INSTALLED_RELEASE = fp.read()
        except IOError as e:
            logger.error("Unable to read previous release from file '%s': %s" %
                         (release_lock_file, e))
            try:
                with open(release_lock_file, "w") as fp:
                    fp.write(speakreader.RELEASE)
            except IOError as e:
                logger.error("Unable to write current release to file '%s': %s" %
                             (release_lock_file, e))

    # Check for new versions
    if speakreader.CONFIG.CHECK_GITHUB_ON_STARTUP and speakreader.CONFIG.CHECK_GITHUB:
        try:
            LATEST_VERSION_HASH = check_update()
        except Exception as e:
            logger.exception("Unhandled exception: %s" % e)
            LATEST_VERSION_HASH = INSTALLED_VERSION_HASH
    else:
        LATEST_VERSION_HASH = INSTALLED_VERSION_HASH

    # Check if the release was updated
    if speakreader.RELEASE != INSTALLED_RELEASE:
        speakreader.CONFIG.UPDATE_SHOW_CHANGELOG = 1
        speakreader.CONFIG.write()
        _UPDATE = True


def getInstalledVersion():

    install_type = current_commit_hash = remote_name = branch_name = None

    if os.path.isdir(os.path.join(speakreader.PROG_DIR, '.git')):
        install_type = 'git'
        output, err = runGit('rev-parse HEAD')

        if output:
            if re.match('^[a-z0-9]+$', output):
                current_commit_hash = output
            else:
                logger.error('Output does not look like a hash, not using it.')
        else:
            logger.error('Could not find latest installed version.')

        if speakreader.CONFIG.DO_NOT_OVERRIDE_GIT_BRANCH and speakreader.CONFIG.GIT_BRANCH:
            branch_name = speakreader.CONFIG.GIT_BRANCH

        else:
            remote_branch, err = runGit('rev-parse --abbrev-ref --symbolic-full-name @{u}')
            remote_branch = remote_branch.rsplit('/', 1) if remote_branch else []
            if len(remote_branch) == 2:
                remote_name, branch_name = remote_branch

            if not remote_name and speakreader.CONFIG.GIT_REMOTE:
                logger.error('Could not retrieve remote name from git. Falling back to %s.' % speakreader.CONFIG.GIT_REMOTE)
                remote_name = speakreader.CONFIG.GIT_REMOTE

            if not remote_name:
                logger.error('Could not retrieve remote name from git. Defaulting to origin.')
                remote_name = 'origin'

            if not branch_name and speakreader.CONFIG.GIT_BRANCH:
                logger.error('Could not retrieve branch name from git. Falling back to %s.' % speakreader.CONFIG.GIT_BRANCH)
                branch_name = speakreader.CONFIG.GIT_BRANCH

            if not branch_name:
                logger.error('Could not retrieve branch name from git. Defaulting to master.')
                branch_name = 'master'

    else:
        install_type = 'source'
        remote_name = 'origin'
        branch_name = speakreader.BRANCH

        version_file = os.path.join(speakreader.PROG_DIR, 'version.txt')

        if os.path.isfile(version_file):
            with open(version_file, 'r') as f:
                current_commit_hash = f.read().strip(' \n\r')

    return install_type, current_commit_hash, remote_name, branch_name


def check_update(auto_update=False, notify=False):
    global INSTALL_TYPE
    global INSTALLED_VERSION_HASH
    global UPDATE_AVAILABLE
    global COMMITS_BEHIND
    global LATEST_RELEASE

    check_github(auto_update=auto_update, notify=notify)

    if not INSTALLED_VERSION_HASH:
        UPDATE_AVAILABLE = None
    elif COMMITS_BEHIND > 0 and speakreader.BRANCH in ('master', 'beta') and \
            speakreader.RELEASE != LATEST_RELEASE:
        speakreader.UPDATE_AVAILABLE = 'release'
    elif COMMITS_BEHIND > 0 and INSTALLED_VERSION_HASH != LATEST_VERSION_HASH and \
            INSTALL_TYPE != 'win':
        UPDATE_AVAILABLE = 'commit'
    else:
        UPDATE_AVAILABLE = False

    # if speakreader.WIN_SYS_TRAY_ICON:
    #     if speakreader.UPDATE_AVAILABLE:
    #         icon = os.path.join(speakreader.PROG_DIR, 'data/interfaces/', speakreader.CONFIG.INTERFACE, 'images/logo_tray-update.ico')
    #         hover_text = speakreader.PRODUCT + ' - Update Available!'
    #     else:
    #         icon = os.path.join(speakreader.PROG_DIR, 'data/interfaces/', speakreader.CONFIG.INTERFACE, 'images/logo_tray.ico')
    #         hover_text = speakreader.PRODUCT + ' - No Update Available'
    #     speakreader.WIN_SYS_TRAY_ICON.update(icon=icon, hover_text=hover_text)


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
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, cwd=speakreader.PROG_DIR)
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


def check_github(auto_update=False, notify=False):
    global INSTALL_TYPE
    global INSTALLED_VERSION_HASH
    global UPDATE_AVAILABLE
    global COMMITS_BEHIND
    global LATEST_RELEASE
    global LATEST_VERSION_HASH

    COMMITS_BEHIND = 0

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

    LATEST_VERSION_HASH = version['sha']
    logger.debug("Latest version is %s", LATEST_VERSION_HASH)

    # See how many commits behind we are
    if not INSTALLED_VERSION_HASH:
        logger.info('You are running an unknown version of SpeakReader. Run the updater to identify your version')
        return

    if LATEST_VERSION_HASH == INSTALLED_VERSION_HASH:
        logger.info('SpeakReader is up to date')
        return

    logger.info('Comparing currently installed version with latest GitHub version')
    url = 'https://api.github.com/repos/%s/%s/compare/%s...%s' % (speakreader.CONFIG.GIT_USER,
                                                                  speakreader.CONFIG.GIT_REPO,
                                                                  LATEST_VERSION_HASH,
                                                                  INSTALLED_VERSION_HASH)
    if speakreader.CONFIG.GIT_TOKEN: url = url + '?access_token=%s' % speakreader.CONFIG.GIT_TOKEN
    response = requests.get(url, timeout=20, whitelist_status_code=404, validator=lambda x: type(x) == dict)

    if response.ok:
        commits = response.json()
    else:
        logger.warn('Could not get commits behind from GitHub.')
        return

    try:
        COMMITS_BEHIND = int(commits['behind_by'])
        logger.debug("In total, %d commits behind", COMMITS_BEHIND)
    except KeyError:
        logger.info('Cannot compare versions. Are you running a local development version?')
        COMMITS_BEHIND = 0

    if COMMITS_BEHIND > 0:
        logger.info('New version is available. You are %s commits behind' % COMMITS_BEHIND)

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

        LATEST_RELEASE = release['tag_name']

        if auto_update:
            logger.info('Running automatic update.')
            #speakreader.shutdown(restart=True, update=True)

    elif COMMITS_BEHIND == 0:
        logger.info('SpeakReader is up to date')


def update():
    if speakreader.INSTALL_TYPE == 'win':
        logger.info('Windows .exe updating not supported yet.')

    elif speakreader.INSTALL_TYPE == 'git':
        output, err = runGit('pull ' + speakreader.CONFIG.GIT_REMOTE + ' ' + speakreader.CONFIG.GIT_BRANCH)

        if not output:
            logger.error('Unable to download latest version')
            return

        for line in output.split('\n'):

            if 'Already up-to-date.' in line:
                logger.info('No update available, not updating')
                logger.info('Output: ' + str(output))
            elif line.endswith(('Aborting', 'Aborting.')):
                logger.error('Unable to update from git: ' + line)
                logger.info('Output: ' + str(output))

    else:
        tar_download_url = 'https://github.com/{}/{}/tarball/{}'.format(speakreader.CONFIG.GIT_USER, speakreader.CONFIG.GIT_REPO, speakreader.CONFIG.GIT_BRANCH)
        update_dir = os.path.join(speakreader.PROG_DIR, 'update')
        version_path = os.path.join(speakreader.PROG_DIR, 'version.txt')

        logger.info('Downloading update from: ' + tar_download_url)
        data = request.request_content(tar_download_url)

        if not data:
            logger.error("Unable to retrieve new version from '%s', can't update", tar_download_url)
            return

        download_name = speakreader.CONFIG.GIT_BRANCH + '-github'
        tar_download_path = os.path.join(speakreader.PROG_DIR, download_name)

        # Save tar to disk
        with open(tar_download_path, 'wb') as f:
            f.write(data)

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
            return
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
                f.write(str(speakreader.LATEST_VERSION))
        except IOError as e:
            logger.error(
                "Unable to write current version to version.txt, update not complete: %s",
                e
            )
            return


def checkout_git_branch():
    if speakreader.INSTALL_TYPE == 'git':
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


def read_changelog(latest_only=False, since_INSTALLED_RELEASE=False):
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
                    elif since_INSTALLED_RELEASE and str(speakreader.INSTALLED_RELEASE) + ' ' in header_text:
                        break

                    output[-1] += '<h' + header_level + '>' + header_text + '</h' + header_level + '>'

                elif line_list_match:
                    line_level = len(line_list_match.group(1)) / 2
                    line_text = line_list_match.group(2)

                    if line_level > prev_level:
                        output[-1] += '<ul>' * (line_level - prev_level) + '<li>' + line_text + '</li>'
                    elif line_level < prev_level:
                        output[-1] += '</ul>' * (prev_level - line_level) + '<li>' + line_text + '</li>'
                    else:
                        output[-1] += '<li>' + line_text + '</li>'

                    prev_level = line_level

                elif line.strip() == '' and prev_level:
                    output[-1] += '</ul>' * (prev_level)
                    output.append('')
                    prev_level = 0

        if since_INSTALLED_RELEASE:
            output.reverse()

        return ''.join(output)

    except IOError as e:
        logger.error('Tautulli Version Checker :: Unable to open changelog file. %s' % e)
        return '<h4>Unable to open changelog file</h4>'
