#!/usr/bin/env python3

import configparser
import sys
import os
import json
import tempfile
import glob


'''Executes and prints a command'''
def execute(cmd):
    print(cmd)
    assert(os.system(cmd) == 0)


def get_filename_body(full_path):
    return os.path.splitext(os.path.basename(full_path))[0]


class App:
    def __init__(self):
        config = configparser.ConfigParser()
        config.read('app.ini')

        app = config['app']
        try:
            self.workspace = app['workspace']
        except:
            self.workspace = None
        self.project = app['project']
        self.project_dir = os.path.dirname(self.project)
        self.scheme = app['scheme']
        self.temp_dir_name = get_filename_body(self.project) + '-' + self.scheme
        self.uses_encryption = app.get('uses encryption', False)
        self.uses_idfa = app.get('uses idfa', False)

        connect = config['connect']
        self.connect_username = connect['username']
        self.connect_team_name = connect['team_name']

        try:
            screenshots = config['screenshots']
            self.screenshot_languages = [x.strip() for x in screenshots['languages'].split(',')]
            self.screenshot_devices = [x.strip() for x in screenshots['devices'].split(',')]
        except KeyError:
            self.screenshot_languages = []
            self.screenshot_devices = []

        submission_information_string = json.dumps({
            'export_compliance_uses_encryption': self.uses_encryption,
            'add_id_info_uses_idfa': self.uses_idfa
        })

        self.deliver_options = f'--force --run_precheck_before_submit false --username {self.connect_username} --team_name "{self.connect_team_name}" --submission_information \'{submission_information_string}\''

        self.actions = {
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
            print(f'Unknown action "{action_name}"')
            self.help()

    def increment_version_number(self):
        execute(f'agvtool ')

    def increment_build_number(self):
        '''Increments the build number of the project'''
        execute(f'fastlane run increment_build_number xcodeproj:"{self.project}"')


    def increment_patch_number(self):
        '''Increments the patch number of the project (e.g. 3.2.x)'''
        execute(f'fastlane run increment_version_number bump_type:patch xcodeproj:"{self.project}"')


    def increment_minor_version(self):
        '''Increments the minor version of the project (e.g. 3.x.1)'''
        execute(f'fastlane run increment_version_number bump_type:minor xcodeproj:"{self.project}"')


    def increment_major_version(self):
        '''Increments the major version of the project (e.g. x.2.1)'''
        execute(f'fastlane run increment_version_number bump_type:major xcodeproj:"{self.project}"')


    def build_ipa(self):
        '''Builds the .ipa file'''
        if self.workspace is not None:
            workspaceParam = f'--workspace {self.workspace}'
        else:
            workspaceParam = ''

        execute(f'fastlane gym {workspaceParam} --scheme "{self.scheme}"')
        #
        # derived_data_dir = os.path.join(os.getenv('HOME'), '.cache/pyfastlane/', self.temp_dir_name)
        # os.makedirs(derived_data_dir, exist_ok=True)
        #
        # execute(f'xcodebuild -workspace {self.workspace} -scheme {self.scheme} -derivedDataPath {derived_data_dir} -destination \'generic/platform=iOS\' build')


    def upload_binary(self):
        '''Uploads the .ipa file to App Store Connect'''
        execute(f'fastlane deliver {self.deliver_options} --skip_screenshots --skip_metadata')


    def upload_metadata(self):
        '''Uploads the metadata to App Store Connect'''
        execute(f'fastlane deliver {self.deliver_options} --skip_binary_upload --skip_screenshots')


    def upload_screenshots(self):
        '''Uploads screenshots to App Store Connect'''
        execute(f'fastlane deliver {self.deliver_options} --skip_binary_upload --skip_metadata --force')


    def replace_screenshots(self):
        '''Replace all screenshots to App Store Connect'''
        execute(f'fastlane deliver {self.deliver_options} --skip_binary_upload --skip_metadata --force --overwrite_screenshots')


    def testflight(self):
        '''Increments build number, builds the .ipa file, then uploads the .ipa file to TestFlight'''
        self.increment_build_number()
        self.build_ipa()
        self.upload_binary()


    def submit(self):
        '''Submits the latest build for the latest version number on App Store Connect'''
        execute(f'fastlane deliver submit_build {self.deliver_options} --skip_screenshots --skip_metadata')


    def release(self):
        '''Increments build number, builds the .ipa file, uploads the metadata and .ipa file, and submits for release on App Store Connect'''
        self.increment_build_number()
        self.build_ipa()
        execute(f'fastlane deliver {self.deliver_options} --submit_for_review --skip_screenshots')

    def snapshot(self):
        '''Capture screenshots using Snapshot'''
        deviceList = ",".join(self.screenshot_devices)

        derived_data_dir = os.path.join(os.getenv('HOME'), '.cache/pyfastlane/', self.temp_dir_name)
        os.makedirs(derived_data_dir, exist_ok=True)

        # Build the app bundle once
        device = self.screenshot_devices[0]

        if self.workspace is not None:
            workspaceParam = f'-workspace {self.workspace}'
        else:
            workspaceParam = ''

        execute(f'xcodebuild {workspaceParam} -scheme "{self.scheme}" -derivedDataPath {derived_data_dir} -destination "platform=iOS Simulator,name={device},OS=14.2" FASTLANE_SNAPSHOT=YES FASTLANE_LANGUAGE=en-US build-for-testing')

        for device in self.screenshot_devices:
            for language in self.screenshot_languages:
                # Skip if we already have >4 screenshots in this directory
                if len(glob.glob(f'fastlane/screenshots/{language}/{device}*')) > 4:
                    print(f'Skipped {device:40}    {language:6}')
                    continue

                if language == 'no':
                    language = 'no-NO'

                if self.workspace is not None:
                    workspaceParam = f'workspace:"{self.workspace}"'
                else:
                    workspaceParam = ''

                execute(f'nice -n 20 fastlane run snapshot {workspaceParam} scheme:"{self.scheme}" devices:"{device}" languages:"{language}" test_without_building:true derived_data_path:"{derived_data_dir}"')

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

app = App()

actions = sys.argv[1:]
if len(actions) == 0:
    actions  = ['help']

for action in actions:
    app.doAction(action)
