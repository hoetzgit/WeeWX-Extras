""" Backup WeeWx."""
# to use add the following to the report services, user.backup.Backup

import time
import datetime
import glob
import json
import os
import shutil
import subprocess

import weewx
from weewx.wxengine import StdService
from weeutil.weeutil import to_bool, option_as_list

VERSION = "0.0.1"

try:
    # Test for new-style weewx logging by trying to import weeutil.logger
    import weeutil.logger
    import logging
    log = logging.getLogger(__name__) # confirm to standards pylint: disable=invalid-name
    def setup_logging(logging_level, config_dict):
        """ Setup logging for running in standalone mode."""
        if logging_level:
            weewx.debug = logging_level

        weeutil.logger.setup('wee_MQTTSS', config_dict)

    def logdbg(msg):
        """ Log debug level. """
        log.debug(msg)

    def loginf(msg):
        """ Log informational level. """
        log.info(msg)

    def logerr(msg):
        """ Log error level. """
        log.error(msg)

except ImportError:
    # Old-style weewx logging
    import syslog
    def setup_logging(logging_level, config_dict): # Need to match signature pylint: disable=unused-argument
        """ Setup logging for running in standalone mode."""
        syslog.openlog('wee_MQTTSS', syslog.LOG_PID | syslog.LOG_CONS)
        if logging_level:
            syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_DEBUG))
        else:
            syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_INFO))

    def logmsg(level, msg):
        """ Log the message at the designated level. """
        # Replace '__name__' with something to identify your application.
        syslog.syslog(level, '__name__: %s' % (msg))

    def logdbg(msg):
        """ Log debug level. """
        logmsg(syslog.LOG_DEBUG, msg)

    def loginf(msg):
        """ Log informational level. """
        logmsg(syslog.LOG_INFO, msg)

    def logerr(msg):
        """ Log error level. """
        logmsg(syslog.LOG_ERR, msg)

class Backup(StdService):
    """Custom service that sounds an alarm if an arbitrary expression evaluates true"""

    def __init__(self, engine, config_dict):
        super(Backup, self).__init__(engine, config_dict)

        loginf("Version is %s" % VERSION)

        service_dict = config_dict.get('Backup', {})
        logdbg("Configuration is %s" % json.dumps(service_dict, default=str))

        enable = to_bool(service_dict.get('enable', True))
        if not enable:
            loginf("Backup is not enabled, exiting")
            return

        self.working_dir = service_dict.get('working_dir', None)
        if self.working_dir is None:
            raise ValueError("A value for 'working_dir' is required.")
        loginf("Working dir is %s." % self.working_dir)

        start = service_dict.get('start', None)
        if start is None:
            raise ValueError("A value for 'start' is required.")
        self.start = datetime.datetime.strptime(start, '%H:%M').time()
        loginf("Start of backup window is %s." % self.start)

        end = service_dict.get('end', None)
        if end is None:
            raise ValueError("A value for 'end' is required.")
        self.end = datetime.datetime.strptime(end, '%H:%M').time()
        loginf("End of backup window is %s." % self.end)

        self.db_names = option_as_list(service_dict.get('db_names', None))
        if self.db_names is None:
            raise ValueError("A value for 'db_names' is required.")
        loginf("Backing up databases: %s." % self.db_names)

        self.db_location = service_dict.get('db_location', 'archive')
        loginf("Database location: %s." % self.db_location)

        self.verbose = service_dict.get('verbose', '')

        self.backup_file = service_dict.get('backup_file', 'last_backup.txt')
        loginf("'backup file': %s." % self.backup_file)

        self.force_backup = to_bool(service_dict.get('force_backup', False))

        self.weewx_root = self.config_dict.get('WEEWX_ROOT', '/home/richbell/weewx-data')

        if not os.path.exists(self.working_dir):
            os.makedirs(self.working_dir)

        self.log_file = os.path.join(self.working_dir, 'backup.txt')
        loginf("'backup log file': %s." % self.log_file)
        self.err_file = os.path.join(self.working_dir, 'backup_err.txt')
        loginf("'backup error file': %s." % self.err_file)

        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)

    def new_archive_record(self, event): # Need to match signature pylint: disable=unused-argument
        """Gets called on a new archive record event."""
        curr_date = datetime.date.today()
        curr_time = self.get_curr_time()

        save_file = os.path.join(self.working_dir, self.backup_file)
        last_run = self.get_last_run(save_file)

        # if the current time is within the start and end range
        # AND if the backup has not run on this date, then do it
        if (self.time_in_range(self.start, self.end, curr_time) and last_run != curr_date) or self.force_backup:
            loginf('Backup started.')
            self.save_last_run(save_file, curr_date)
            self.do_backup()
            loginf('Backup completed..')

    def get_curr_time(self):
        """" Get the current time. """
        curr_hr = time.strftime("%H")
        curr_min = time.strftime("%M")
        curr_sec = time.strftime("%S")
        curr_time = datetime.time(int(curr_hr), int(curr_min), int(curr_sec))
        return curr_time

    def time_in_range(self, start, end, value):
        """Return true if value is in the range [start, end]"""
        #logdbg(' **** Backup date check %s %s %s' % (start, end, value))
        if start <= end:
            return start <= value <= end
        return start <= value or value <= end

    def save_last_run(self, save_file, last_run):
        """ Save date/time of last backup. """
        file_ptr = open(save_file, "w")
        file_ptr.write(str(last_run))
        file_ptr.close()

    def get_last_run(self, save_file):
        """ Get date of last backup. """
        try:
            file_ptr = open(save_file, "r")
        except FileNotFoundError:
            last_run = datetime.date.today()
            loginf("Lastrun not found, setting to today: %s" %last_run)
            self.save_last_run(save_file, last_run)
            return last_run
        line = file_ptr.read()
        file_ptr.close()
        temp = line.split('-')
        return datetime.date(int(temp[0]), int(temp[1]), int(temp[2]))

    def do_backup(self):
        """ Backup WeeWX configuration, data (DB), and code. """
        now = datetime.datetime.now()
        day_of_week = str(datetime.datetime.today().weekday())
        curr_dir = os.path.join(self.working_dir, 'bkup' + day_of_week)
        logdbg("Current backup directory %s." % curr_dir)
        prev_dir = os.path.join(self.working_dir, 'prevbkup' + day_of_week)
        logdbg("Previous backup directory %s." % prev_dir)

        log_file_ptr = open(self.log_file, "w")
        log_file_ptr.write("%s\n" % now)
        err_file_ptr = open(self.err_file, "w")
        err_file_ptr.write("%s\n" % now)

        # ToDo - eliminate directory change?
        cwd = os.getcwd()
        os.chdir(self.working_dir)

        self.rotate_dirs(prev_dir, curr_dir)
        self.backup_code(os.path.join(self.weewx_root, '*'), curr_dir, log_file_ptr, err_file_ptr)

        os.makedirs(os.path.join(curr_dir, self.db_location))
        for db_name in self.db_names:
            db_file_name = os.path.join(self.weewx_root, self.db_location, db_name)
            self.check_db(db_file_name, log_file_ptr, err_file_ptr)
            self.backup_db(db_file_name, os.path.join(curr_dir, self.db_location, db_name), log_file_ptr, err_file_ptr)
            self.check_db(os.path.join(curr_dir, self.db_location, db_name), log_file_ptr, err_file_ptr)

        os.chdir(cwd)

        log_file_ptr.close()
        err_file_ptr.close()

    def check_db(self, db_file, log_file_ptr, err_file_ptr):
        """ Check the database. """
        cmd = ['sqlite3', '-line']
        cmd.extend([db_file])
        cmd.extend(['pragma integrity_check'])
        logdbg("%s" % cmd)

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        return_code = process.returncode

        if return_code != 0:
            logerr("%s had a return code of %s" % (cmd, return_code))
            logerr("%s" % stderr)

        log_file_ptr.write("%s\n" % db_file)
        log_file_ptr.write(stdout.decode("utf-8"))
        err_file_ptr.write("%s\n" % db_file)
        err_file_ptr.write(stderr.decode("utf-8"))

    # ToDo - handle db name 'as monitor', perhaps just use a 'hard coded' value, 'working_db'?
    def backup_db(self, db_file, backup_db, log_file_ptr, err_file_ptr):
        """" Backup a WeeWX database. """
        cmd = ['sqlite3']
        cmd.extend([ '-cmd', 'attach "' + db_file + '" as monitor'])
        cmd.extend(['-cmd', '.backup monitor ' + backup_db])
        cmd.extend(['-cmd', 'detach monitor'])
        logdbg("%s" % cmd)

        process = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        return_code = process.returncode

        if return_code != 0:
            logerr("%s had a return code of %s" % (cmd, return_code))
            logerr("%s" % stderr)

        log_file_ptr.write(stdout.decode("utf-8"))
        err_file_ptr.write(stderr.decode("utf-8"))

    def backup_code(self, source_dir, dest_dir, log_file_ptr, err_file_ptr):
        """ Backup the code."""
        cmd = ['rsync', '-p', '-a', '-L', self.verbose]
        cmd.extend(['--exclude=.Trash*/',
                    '--exclude=weewx_bkup/',
                    '--exclude=archive*/',
                    '--exclude=run/',
                    '--exclude=lost+found/',
                    '--exclude=.git/'])
        cmd.extend(glob.glob(source_dir))
        cmd.extend([dest_dir])
        logdbg("%s" % cmd)

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        return_code = process.returncode

        if return_code != 0:
            logerr("%s had a return code of %s" % (cmd, return_code))
            logerr("%s" % stderr)

        log_file_ptr.write(stdout.decode("utf-8"))
        err_file_ptr.write(stderr.decode("utf-8"))

    def rotate_dirs(self, prev_dir, curr_dir):
        """ Rotate the backup directories."""
        try:
            shutil.rmtree(prev_dir)
        except FileNotFoundError as exception:
            loginf("Directory %s does not exist," % prev_dir)
            logdbg("Directory delete failed : (%d) %s\n" % (exception.errno, exception.strerror))

        try:
            shutil.move(curr_dir, prev_dir)
        except FileNotFoundError as exception:
            loginf("Directory %s does not exist," % prev_dir)
            logdbg("Directory delete failed : (%d) %s\n" % (exception.errno, exception.strerror))

if __name__ == "__main__":
    import configobj
    import argparse
    def main():
        """ Run the service 'standalone'. """
        usage = ""

        parser = argparse.ArgumentParser(usage=usage)
        parser.add_argument("--force-backup", action="store_true", dest="force_backup",
                            help="Force the backup to run.")
        parser.add_argument("--enable", action="store_true", dest="enable",
                            help="Override the configuration'enable' flag.")
        parser.add_argument("config_file")

        options = parser.parse_args()

        config_path = os.path.abspath(options.config_file)
        config_dict = configobj.ConfigObj(config_path, file_error=True)

        if options.force_backup:
            config_dict.merge({'Backup': {'force_backup': True}})
        if options.enable:
            config_dict.merge({'Backup': {'enable': True}})

        weeutil.logger.setup('wee_backup', config_dict)

        config_dict['Engine']['Services'] = {}
        engine = weewx.engine.DummyEngine(config_dict)

        backup = Backup(engine, config_dict)

        if to_bool(config_dict['Backup'].get('enable', False)):
            event = weewx.Event(weewx.NEW_ARCHIVE_RECORD, record={'dateTime': int(time.time())})
            backup.new_archive_record(event)

    main()
