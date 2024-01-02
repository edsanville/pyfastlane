#!/usr/bin/env python3

import configparser
import os
import json
import glob
import argparse
import os.path
import subprocess
import logging
import pytz

import appPublish
import appstoreconnect

from munch import DefaultMunch
from pprint import pprint
from functools import *
from datetime import datetime

'''Executes and prints a command'''
def execute(cmd, silent=True):
    output_filename = 'command.log'
    logging.info(cmd)
    if silent:
        cmd += f' > {output_filename} 2>&1'
    result = os.system(cmd)
    if result != 0:
        logging.error(f'Command failed: {cmd}')
        logging.error(f'Exit code: {result}')
        logging.error(f'Output is in file {output_filename}')
        exit(1)


def git_is_clean():
    cmd = 'git status --porcelain'
    logging.info(cmd)
    try:
        proc = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE)
        return len(proc.stdout.readlines()) == 0
    except FileNotFoundError as e:
        logging.error(e)
        exit(1)


def git_commit(msg):
    execute(f'git commit -a -m "{msg}"')


def get_filename_body(full_path):
    return os.path.splitext(os.path.basename(full_path))[0]


class App:
    config: appPublish.Config

    def __init__(self, path: str):
        self.path = path
        parser = configparser.ConfigParser()
        iniPath = os.path.join(path, 'app.ini')
        successfullyReadFilenames = parser.read(iniPath)
        if len(successfullyReadFilenames) < 1:
            logging.error(f'Cannot read: {iniPath}')
            exit(1)

        config: appPublish.Config = DefaultMunch.fromDict(dict(parser))
        self.config = config

        self.config.project_dir = os.path.dirname(self.config.app.project)
        self.temp_dir_name = get_filename_body(self.config.app.project) + '-' + self.config.app.scheme

        try:
            self.screenshot_languages = [x.strip() for x in config.screenshots.languages.split(',')]
            self.screenshot_devices = [x.strip() for x in config.screenshots.devices.split(',')]
        except KeyError:
            self.screenshot_languages = []
            self.screenshot_devices = []

        submission_information_string = json.dumps({
            'export_compliance_uses_encryption': self.config.app.uses_encryption or False,
            'add_id_info_uses_idfa': self.config.app.uses_idfa or False
        })

        deliver_options = [
            '--force',
            '--run_precheck_before_submit false',
            f'--username {self.config.connect.username}',
            f'--team_name "{self.config.connect.team_name}"',
            f'--submission_information \'{submission_information_string}\'',
            f'--metadata_path \'{self.path}/fastlane/metadata\'',
            f'--app_identifier {self.config.app.bundle_id}'
        ]

        self.deliver_options = ' '.join(deliver_options)

        self.actions = {
            'versions': self.show_version_information,
            'increment_build_number': self.increment_build_number,
            'increment_patch_number': self.increment_patch_number,
            'increment_minor_version': self.increment_minor_version,
            'increment_major_version': self.increment_major_version,
            'build': self.build_ipa,
            'upload_binary': self.upload_binary,
            'upload_metadata': self.upload_metadata,
            'upload_screenshots': self.upload_screenshots,
            'replace_screenshots': self.replace_screenshots,
            'testflight': self.testflight,
            'submit': self.submit,
            'release': self.release,
            'snapshot': self.snapshot,
            'help': self.help
        }


    def doAction(self, action_name):
        try:
            action = self.actions[action_name]
            action()
        except KeyError:
            logging.error(f'Unknown action "{action_name}"')
            self.help()

    def _get_version_number(self):
        cmd = 'agvtool what-marketing-version -terse'.split()
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        for lineBytes in proc.stdout:
            line = lineBytes.decode()
            version_string = line[line.rfind('=') + 1:].strip()
            return version_string

    def _get_build_number(self):
        cmd = 'agvtool what-version -terse'.split()
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        for lineBytes in proc.stdout:
            version_string = lineBytes.decode().strip()
            return version_string


    def ensure_git_clean(self):
        if not git_is_clean():
            logging.error('Dirty directory:  uncommitted git changes!')
            exit(1)


    def tag_commit(self, tag_name: str):
        logging.info(f'Tagging commit as {tag_name}')
        execute(f'git tag -f {tag_name}')


    def show_version_information(self):
        '''Shows version information from the project and from App Store Connect'''
        def localTimeString(isoString: str):
            DATE_FORMAT = '%Y-%m-%d %H:%M:%S %Z'
            return datetime.fromisoformat(isoString).astimezone().strftime(DATE_FORMAT)

        session = appstoreconnect.Session()
        latest_build: appstoreconnect.Build = None

        print(f'{"":15s} {"Version":12s} {"Date":25s} {"Build":12s} {"Date":25s}')

        print(f'{"Project":15s} {self._get_version_number():12s} {"":25s} {self._get_build_number():12s}')

        builds = session.get_builds(self.config.app.app_id)
        try:
            latest_build = max(builds, key=lambda b: b.attributes.uploadedDate)
            app_store_build = latest_build.attributes.version
            app_store_build_date = localTimeString(latest_build.attributes.uploadedDate)
        except:
            app_store_build = 'None'
            app_store_build_date = ''

        versions = session.get_appStoreVersions(self.config.app.app_id)
        try:
            latest_version = max(versions, key=lambda version: version.attributes.createdDate)
            app_store_version = latest_version.attributes.versionString
            app_store_version_date = localTimeString(latest_version.attributes.createdDate)
        except ValueError:
            app_store_version = 'None'
            app_store_version_date = ''

        print(f'{"App Store":15s} {app_store_version:12s} {app_store_version_date:25s} {app_store_build:12s} {app_store_build_date:25s}')
        

    def increment_build_number(self):
        '''Increments the build number of the project'''
        execute(f'agvtool next-version -all')
        git_commit('Bump version number')


    def increment_patch_number(self):
        '''Increments the patch number of the project (e.g. 3.2.x)'''
        execute(f'fastlane run increment_version_number bump_type:patch xcodeproj:"{self.config.app.project}"')


    def increment_minor_version(self):
        '''Increments the minor version of the project (e.g. 3.x.1)'''
        execute(f'fastlane run increment_version_number bump_type:minor xcodeproj:"{self.config.app.project}"')


    def increment_major_version(self):
        '''Increments the major version of the project (e.g. x.2.1)'''
        execute(f'fastlane run increment_version_number bump_type:major xcodeproj:"{self.config.app.project}"')


    def build_ipa(self):
        '''Builds the .ipa file'''
        if self.config.app.workspace is not None:
            workspaceParam = f'--workspace {self.config.app.workspace}'
        else:
            workspaceParam = ''

        execute(f'fastlane gym {workspaceParam} --scheme "{self.config.app.scheme}"')
        #
        # derived_data_dir = os.path.join(os.getenv('HOME'), '.cache/pyfastlane/', self.temp_dir_name)
        # os.makedirs(derived_data_dir, exist_ok=True)
        #
        # execute(f'xcodebuild -workspace {self.config.app.workspace} -scheme {self.config.app.scheme} -derivedDataPath {derived_data_dir} -destination \'generic/platform=iOS\' build')


    def upload_binary(self):
        '''Uploads the .ipa file to App Store Connect'''
        execute(f'fastlane deliver {self.deliver_options} --skip_screenshots --skip_metadata')
        self.tag_commit(self._get_version_number())


    def upload_metadata(self):
        '''Uploads the metadata to App Store Connect'''
        execute(f'fastlane deliver {self.deliver_options} --skip_binary_upload --skip_screenshots', silent=False)
        self.tag_commit(self._get_version_number())


    def upload_screenshots(self):
        '''Uploads screenshots to App Store Connect'''
        execute(f'fastlane deliver {self.deliver_options} --skip_binary_upload --skip_metadata --force')
        self.tag_commit(self._get_version_number())


    def replace_screenshots(self):
        '''Replace all screenshots to App Store Connect'''
        execute(f'fastlane deliver {self.deliver_options} --skip_binary_upload --skip_metadata --force --overwrite_screenshots')
        self.tag_commit(self._get_version_number())


    def testflight(self):
        '''Increments build number, builds the .ipa file, then uploads the .ipa file to TestFlight'''
        self.ensure_git_clean()
        self.increment_build_number()
        self.build_ipa()
        self.upload_binary()


    def submit(self):
        '''Submits the latest build for the latest version number on App Store Connect'''
        execute(f'fastlane deliver submit_build {self.deliver_options} --skip_screenshots --skip_metadata', silent=False)


    def release(self):
        '''Increments build number, builds the .ipa file, uploads the metadata and .ipa file, and submits for release on App Store Connect'''
        self.increment_build_number()
        self.build_ipa()
        execute(f'fastlane deliver {self.deliver_options} --submit_for_review --skip_screenshots')
        self.tag_commit(self._get_version_number())

    def snapshot(self):
        '''Capture screenshots using Snapshot'''
        deviceList = ",".join(self.screenshot_devices)

        derived_data_dir = os.path.join(os.getenv('HOME'), '.cache/pyfastlane/', self.temp_dir_name)
        os.makedirs(derived_data_dir, exist_ok=True)

        # Build the app bundle once
        device = self.screenshot_devices[0]

        if self.config.app.workspace is not None:
            workspaceParam = f'-workspace {self.config.app.workspace}'
        else:
            workspaceParam = ''

        execute(f'xcodebuild {workspaceParam} -scheme "{self.config.app.scheme}" -derivedDataPath {derived_data_dir} -destination "platform=iOS Simulator,name={device},OS=14.2" FASTLANE_SNAPSHOT=YES FASTLANE_LANGUAGE=en-US build-for-testing')

        for device in self.screenshot_devices:
            for language in self.screenshot_languages:
                # Skip if we already have >4 screenshots in this directory
                if len(glob.glob(f'fastlane/screenshots/{language}/{device}*')) > 4:
                    logging.warning(f'Skipped {device:40}    {language:6}')
                    continue

                if language == 'no':
                    language = 'no-NO'

                if self.config.app.workspace is not None:
                    workspaceParam = f'workspace:"{self.config.app.workspace}"'
                else:
                    workspaceParam = ''

                execute(f'nice -n 20 fastlane run snapshot {workspaceParam} scheme:"{self.config.app.scheme}" devices:"{device}" languages:"{language}" test_without_building:true derived_data_path:"{derived_data_dir}"')

                # Sigh, we need to move "no-NO" to "no"
                if language == 'no-NO':
                    execute('rsync -r fastlane/screenshots/no-NO fastlane/screenshots/no')
                    execute('rm -rf fastlane/screenshots/no-NO')


    def help(self):
        '''Shows available actions'''
        print('Available actions:')
        actions = self.actions
        for action_name in actions:
            print(f'{action_name:25}: {actions[action_name].__doc__}')


# Main

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Publish apps to App Store Connect')
    parser.add_argument('path', help='Path to directory containing the app.ini file')
    parser.add_argument('actions', nargs='*', help='Action(s) to take')
    parser.add_argument('-d', type=bool, dest='debug', help='Log more for debugging purposes')
    args = parser.parse_args()

    # Setup logging
    log_format = '%(asctime)s %(levelname)8s %(message)s'
    if args.debug:
        logging.basicConfig(level=logging.DEBUG, format=log_format)
    else:
        logging.basicConfig(level=logging.INFO, format=log_format)

    app = App(args.path)

    actions = args.actions
    if len(actions) == 0:
        actions  = ['help']

    for action in actions:
        app.doAction(action)
