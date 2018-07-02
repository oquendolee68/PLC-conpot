"""
Conpot FTP Handlers.
-  FTPCommandChannel : For handling FTP commands
-  FTPDataTransferChannel: For handling Data Transfer - Active/Passive Mode.
"""
from conpot.protocols.ftp.base_handler import FTPHandlerBase
import logging
import fs
import glob
from fs import errors
logger = logging.getLogger(__name__)


# all commands:
ftp_commands = {
   'ABOR': {
        'auth': True,                              # <-| Does the command require any kind of auth
        'perm': None,                              # <-| What kind of permissions are required to execute this command
        'args': False,                             # <-| Whether command requires any arguments
        'help': 'Syntax: ABOR (abort transfer).'   # <-| Valid command syntax. For help.
    },
   'CDUP': dict(perm='e', auth=True, arg=False, help='Syntax: CDUP (go to parent directory).'),
   'CWD': dict(perm='e', auth=True, arg=None, help='Syntax: CWD [<SP> dir-name] (change working directory).'),
   'DELE': dict(perm='d', auth=True, arg=True, help='Syntax: DELE <SP> file-name (delete file).'),
   'HELP': dict(perm=None, auth=False, arg=None, help='Syntax: HELP [<SP> cmd] (show help).'),
   'LIST': dict(perm='l', auth=True, arg=None, help='Syntax: LIST [<SP> path] (list files).'),
   'MDTM': dict(perm='l', auth=True, arg=True, help='Syntax: MDTM [<SP> path] (file last modification time).'),
   'MODE': dict(perm=None, auth=True, arg=True, help='Syntax: MODE <SP> mode (noop; set data transfer mode).'),
   'MKD': dict(perm='m', auth=True, arg=True, help='Syntax: MKD <SP> path (create directory).'),
   'NLST': dict(perm='l', auth=True, arg=None, help='Syntax: NLST [<SP> path] (list path in a compact form).'),
   'NOOP': dict(perm=None, auth=False, arg=False, help='Syntax: NOOP (just do nothing).'),
   'PASS': dict(perm=None, auth=False, arg=None, help='Syntax: PASS [<SP> password] (set user password).'),
   'PASV': dict(perm=None, auth=True, arg=False, help='Syntax: PASV (open passive data connection).'),
   'PORT': dict(perm=None, auth=True, arg=True, help='Syntax: PORT <sp> h,h,h,h,p,p (open active data connection).'),
   'PWD': dict(perm=None, auth=True, arg=False, help='Syntax: PWD (get current working directory).'),
   'QUIT': dict(perm=None, auth=False, arg=False, help='Syntax: QUIT (quit current session).'),
   'REIN': dict(perm=None, auth=True, arg=False, help='Syntax: REIN (flush account).'),
   'RETR': dict(perm='r', auth=True, arg=True, help='Syntax: RETR <SP> file-name (retrieve a file).'),
   'RMD': dict(perm='d', auth=True, arg=True, help='Syntax: RMD <SP> dir-name (remove directory).'),
   'RNFR': dict(perm='f', auth=True, arg=True, help='Syntax: RNFR <SP> file-name (rename (source name)).'),
   'RNTO': dict(perm='f', auth=True, arg=True, help='Syntax: RNTO <SP> file-name (rename (destination name)).'),
   'SITE': dict(perm=None, auth=False, arg=True, help='Syntax: SITE <SP> site-command (execute SITE command).'),
   'SITE HELP': dict(perm=None, auth=False, arg=None, help='Syntax: SITE HELP [<SP> cmd] (show SITE command help).'),
   'SITE CHMOD': dict(perm='M', auth=True, arg=True, help='Syntax: SITE CHMOD <SP> mode path (change file mode).'),
   'SIZE': dict(perm='l', auth=True, arg=True, help='Syntax: SIZE <SP> file-name (get file size).'),
   'STAT': dict(perm='l', auth=False, arg=None, help='Syntax: STAT [<SP> path name] (server stats [list files]).'),
   'STOR': dict(perm='w', auth=True, arg=True, help='Syntax: STOR <SP> file-name (store a file).'),
   'STOU': dict(perm='w', auth=True, arg=None, help='Syntax: STOU [<SP> name] (store a file with a unique name).'),
   'STRU': dict(perm=None, auth=True, arg=True, help='Syntax: STRU <SP> type (noop; set file structure).'),
   'SYST': dict(perm=None, auth=False, arg=False, help='Syntax: SYST (get operating system type).'),
   'TYPE': dict(perm=None, auth=True, arg=True, help='Syntax: TYPE <SP> [A | I] (set transfer type).'),
   'USER': dict(perm=None, auth=False, arg=True, help='Syntax: USER <SP> user-name (set username).'),
   'XCUP': dict(perm='e', auth=True, arg=False, help='Syntax: XCUP (obsolete; go to parent directory).'),
   'XCWD': dict(perm='e', auth=True, arg=None, help='Syntax: XCWD [<SP> dir-name] (obsolete; change directory).'),
   'XMKD': dict(perm='m', auth=True, arg=True, help='Syntax: XMKD <SP> dir-name (obsolete; create directory).'),
   'XPWD': dict(perm=None, auth=True, arg=False, help='Syntax: XPWD (obsolete; get current dir).'),
   'XRMD': dict(perm='d', auth=True, arg=True, help='Syntax: XRMD <SP> dir-name (obsolete; remove directory).'),
}


class FTPCommandChannel(FTPHandlerBase):
    """
        FTP Command Responder. Partial implementation of RFC 959.
    """
    # TODO: FTP over SSL?
    # only commands that are enabled should be assigned here to commands! To be configured in the Server class.
    commands = ftp_commands

    # clean things, sanity checks and more
    def _pre_process_cmd(self, line, cmd, arg):
        kwargs = {}
        if cmd == "SITE" and arg:
            cmd = "SITE %s" % arg.split(' ')[0].upper()
            arg = line[len(cmd) + 1:]

        logger.info('Received command {} : {} from FTP client {}: {}'.format(cmd, line, self.client_address,
                                                                             self.session.id))

        # Recognize those commands having a "special semantic". They
        # should be sent by following the RFC-959 procedure of sending
        # Telnet IP/Synch sequence (chr 242 and 255) as OOB data but
        # since many ftp clients don't do it correctly we check the
        # last 4 characters only.
        if cmd not in self.commands:
            if cmd[-4:] in ('ABOR', 'STAT', 'QUIT'):
                cmd = cmd[-4:]
            else:
                self.respond(b'500 Command %a not understood' % cmd)
                return

        # - checking for valid arguments
        if not arg and self.commands[cmd]['arg'] == True:  # NOQA
            self.respond(b"501 Syntax error: command needs an argument")
            return
        if arg and self.commands[cmd]['arg'] == False:  # NOQA
            self.respond(b'501 Syntax error: command does not accept arguments.')
            return

        if not self.authenticated:
            if self.commands[cmd]['auth'] or (cmd == 'STAT' and arg):
                self.respond(b'530 Log in with USER and PASS first.')
                return
            else:
                # call the proper ftp_* method
                self._process_command(cmd, arg)
                return
        else:
            if (cmd == 'STAT') and not arg:
                self.ftp_STAT()
                return

            # for file-system related commands check whether real path
            # destination is valid
            if self.commands[cmd]['perm'] and (cmd != 'STOU'):
                if cmd in ('CWD', 'XCWD'):
                    arg = self.config.ftp_fs.validatepath(arg or '/')
                elif cmd in ('CDUP', 'XCUP'):
                    try:
                        arg = self.config.ftp_fs.validatepath('..')
                    except fs.errors.IllegalBackReference:
                        # Trying to access the directory which the current user has no access to
                        # TODO: what to respond here? For now just terminate the session
                        self.disconnect_client = True
                        return
                elif cmd == 'LIST':
                    if arg.lower() in ('-a', '-l', '-al', '-la'):
                        arg = self.config.ftp2fs(self.config.cwd)
                    else:
                        arg = self.config.ftp2fs(arg or self.config.cwd)
                    return
                elif cmd == 'STAT':
                    if glob.has_magic(arg):
                        self.respond(b'550 Globbing not supported.')
                        return
                    arg = self.config.ftp2fs(arg or self.config.cwd)
                elif cmd == 'SITE CHMOD':
                    if ' ' not in arg:
                        self.respond(b'501 Syntax error: command needs two arguments.')
                        return
                    else:
                        mode, arg = arg.split(' ', 1)
                        arg = self.config.ftp2fs(arg)
                        kwargs = dict(mode=mode)
                else:
                    arg = self.config.ftp2fs(arg or self.config.cwd)
                    # FIXME: hack for MKD
                    arg = line.split(' ', 1)[1] if arg is None else arg

                if not self.config.ftp_fs.validatepath(arg):
                    line = self.config.fs2ftp(arg)
                    self.respond(b'550 %a points to a path which is outside the user\'s root directory.' % line)
                    return

            # check permission
            perm = self.commands[cmd]['perm']
            if perm is not None and cmd != 'STOU':
                if not self.config.authorizer_has_perm(self.username, perm, arg):
                    self.respond(b'550 Not enough privileges.')
                    return

            # call the proper ftp_* method
            self._process_command(cmd, arg, **kwargs)

    def _process_command(self, cmd, *args, **kwargs):
        """Process command by calling the corresponding ftp_* class method (e.g. for received command "MKD pathname",
        ftp_MKD() method is called with "pathname" as the argument).
        """
        if self.invalid_login_attempt > self.max_login_attempts:
            self.respond(b'550 Permission denied. (Exceeded maximum permitted login attempts)')
            self.disconnect_client = True
        else:
            method = getattr(self, 'ftp_' + cmd.replace(' ', '_'))
            self._last_command = cmd
            method(*args, **kwargs)
            if self._last_response:
                code = int(self._last_response[:3])
                resp = self._last_response[4:]
                logger.debug('Last response {}:{} Client {}:{}'.format(code, resp, self.client_address, self.session.id))

    # - main command processor
    def process_ftp_command(self):
        """
        Handle an incoming handle request - pick and item from the input_q, reads the contents of the message and
        dispatch contents to the appropriate ftp_* method.
        :param: (bytes) line - incoming request
        :return: (bytes) response - reply in respect to the request
        """
        try:
            # decoding should be done using utf-8
            line = self._input_q.get().decode()
            # Remove any CR+LF if present
            line = line[:-2] if line[-2:] == '\r\n' else line
            if line:
                cmd = line.split(' ')[0].upper()
                arg = line[len(cmd) + 1:]
                try:
                    self._pre_process_cmd(line, cmd, arg)
                except UnicodeEncodeError:
                    # FIXME: "501 can't decode path (server filesystem encoding "is %s)" % sys.getfilesystemencoding()
                    self.respond(b'501 can\'t decode path (server filesystem encoding _ ')

        except UnicodeDecodeError:
            # RFC-2640 doesn't mention what to do in this case. So we'll just return 501
            self.respond(b"501 can't decode command.")

    # ----------------------- Not Implemented Commands ------------------------

    # - more common commands
    def ftp_ABOR(self, arg):
        """
            Aborts a file transfer currently in progress.
            Authentication required: YES
            Permissions: None
            Syntax: ABOR (abort transfer)
        """
        # There are 3 cases here.
        # case 1: ABOR while no data channel is opened : return 225
        # case 2: user sends a PASV, a data-channel socket is listening data but not connected, and ABOR is sent:
        #  - close the listening data socket and respond with 225
        # case 3: data channel opened with PASV, or PORT, but ABOR is sent before a data transfer has been started
        #  - close the listening data socket and respond with 225
        # case 4: ABOR while a data transfer on DTP channel is in progress:
        #  - close data channel, respond with 426, respond with 226.
        # TODO: write tests with incomplete transfer.
        pass

    def ftp_LIST(self, path):
        pass

    def ftp_MDTM(self):
        pass

    def ftp_NLST(self):
        """Return a list of files in the specified directory in a compact form to the client."""
        pass

    def ftp_PASV(self):
        pass

    def ftp_PORT(self, arg):
        """
        Connects to remote client and dispatches the resulting connection to DTPHandler.
        :param arg:
        :return:
        """
        # if self.mode == 'PASV':
        #     self.client_sock.close()
        #     self.mode = 'PORT'
        # try:
        #     portlist = arg.split(',')
        # except ValueError:
        #     return b'501 Bad syntax for PORT.'
        # if len(portlist) != 6:
        #     return b'501 Bad syntax for PORT.'
        # self.cli_ip = '.'.join(portlist[:4])
        # self.cli_port = (int(portlist[4]) << 8) + int(portlist[5])
        # return b'200 PORT Command Successful'
        pass

    def ftp_RETR(self):
        pass

    def ftp_RNFR(self):
        pass

    def ftp_RNTO(self):
        pass

    def ftp_SITE_CHMOD(self, arg):
        pass

    def ftp_SITE_HELP(self, line):
        """Return help text to the client for a given SITE command."""
        pass

    def ftp_STOR(self):
        pass

    # - less common commands
    def ftp_STAT(self):
        pass

    def ftp_REIN(self, arg):
        pass

    def ftp_SIZE(self, path):
        """Return size of file in a format suitable for using with RESTart as defined in RFC-3659.

        Implementation note: properly handling the SIZE command when TYPE ASCII is used would require to scan the
        entire file to perform the ASCII translation logic (file.read().replace(os.linesep, '\r\n')) and then
        calculating the len of such data which may be different than the actual size of the file on the server.
        Considering that calculating such result could be very resource-intensive and also dangerous (DoS) we reject
        SIZE when the current TYPE is ASCII. However, clients in general should not be resuming downloads
        in ASCII mode.  Resuming downloads in binary mode is the recommended way as specified in RFC-3659.
        """
        line = self.config.fs2ftp(path)
        if self._current_type == 'a':
            self.respond(b'550 SIZE not allowed in ASCII mode.')
        # If the file is a sym-link i.e. not readable, send not retrievable
        if not self.config.ftp_fs.isfile(self.config.ftp_fs.realpath(path)):
            self.respond(b'550 is not retrievable.')
        try:
            assert isinstance(path, str)
            size = self.config.ftp_fs.getsize(path)
        except (OSError, fs.errors.FSError) as err:
            self.respond(b'550 %a.' % str(err))
        else:
            self.respond(b'213 %a' % size)

    # ------------------------------ Implemented Commands -------------------------------

    def ftp_MKD(self, path):
        """Create the specified directory. On success return the directory path, else None.
        """
        # line = self.config.fs2ftp(path)
        try:
            self.config.ftp_fs.mkdir(path)
        except (OSError, fs.errors.FSError) as err:
            self.respond(b'550 %a.' % err)
        else:
            # The 257 response is supposed to include the directory
            # name and in case it contains embedded double-quotes
            # they must be doubled (see RFC-959, chapter 7, appendix 2).
            self.respond(b'257 "%a" directory created.' % path.replace('"', '""'))

    def ftp_RMD(self, path):
        """Remove the specified directory. On success return the directory path, else None.
        """
        if self.config.ftp_fs.realpath(path) == self.config.realpath(self.config.ftp_home):
            self.respond(b'550 Can\'t remove root directory.')
        try:
            self.config.ftp_fs.rmdir(path)
        except (OSError, fs.errors.FSError) as err:
            self.respond(b'550 %a.' % str(err))
        else:
            self.respond(b'250 Directory removed.')

    def ftp_CDUP(self, path):
        """Change into the parent directory.
        On success return the new directory, else None.
        """
        # Note: RFC-959 says that code 200 is required but it also says
        # that CDUP uses the same codes as CWD.
        return self.ftp_CWD(path)

    def ftp_PWD(self, arg):
        """Return the name of the current working directory to the client."""
        cwd = self.config.ftp_fs.getcwd()
        try:
            assert isinstance(cwd, str), cwd
        except AssertionError:
            logger.info('FTP CWD not unicode.')
        finally:
            self.respond(b'257 "%a" is the current directory.' % cwd.replace('"', '""'))

    def ftp_CWD(self, path):
        """Change the current working directory."""
        # Temporarily join the specified directory to see if we have permissions to do so, then get back to original
        # process's current working directory.
        init_cwd = self.config.ftp_fs.getcwd()
        try:
            assert path, isinstance(path, str)
            self.config.ftp_fs.chdir(path)
        except AssertionError as err:
            logger.info('Client {} requested non-unicode path: {} for CWD'.format(self.client_address, path))
            self.respond(b'550 %a.' % str(err))
        except fs.errors.FSError as fs_err:
            logger.info('Client {} requested path: {} does not exists'.format(self.client_address, path))
            self.respond(b'550 %a.' % str(fs_err))
        except (fs.errors.PermissionDenied, fs.errors.IllegalBackReference):
            # TODO: log user as well.
            logger.info('Client {} requested path: {} trying to access directory to which it has no access to.'.format(
                self.client_address, path)
            )
            self.respond(b'500 Permission denied')
        else:
            logger.info('Changing current directory {} to {}'.format(init_cwd, init_cwd+path))
            self.respond(b'250 "%s" is the current directory.' % path)

    def ftp_DELE(self, path):
        """Delete the specified file."""
        try:
            self.config.ftp_fs.remove(path)
        except (OSError, fs.errors.FSError) as err:
            why = str(err)
            # FIXME: This could potentially tell the user that we are a honeypot.
            self.respond(b'550 %a.' % why)
        else:
            self.respond(b'250 File removed.')

    def ftp_ALLO(self, line):
        """Allocate bytes for storage (noop)."""
        # not necessary (always respond with 202)
        self.respond(b'202 No storage allocation necessary.')

    def ftp_NOOP(self, line):
        """Do nothing."""
        self.respond(b'200 I successfully done nothin\'.')

    def ftp_MODE(self, line):
        """Set data transfer mode ("S" is the only one supported (noop))."""
        mode = line.upper()
        if mode == 'S':
            self.respond(b'200 Transfer mode set to: S')
        elif mode in ('B', 'C'):
            self.respond(b'504 Unimplemented MODE type.')
        else:
            self.respond(b'501 Unrecognized MODE type.')

    def ftp_TYPE(self, line):
        """Set current type data type to binary/ascii"""
        data_type = line.upper().replace(' ', '')
        if data_type in ("A", "L7"):
            self.respond(b'200 Type set to: ASCII.')
            self._current_type = 'a'
        elif data_type in ("I", "L8"):
            self.respond(b'200 Type set to: Binary.')
            self._current_type = 'i'
        else:
            self.respond(b'504 Unsupported type "%a".' % line)

    def ftp_QUIT(self, arg):
        self.respond(b'221 Bye.')
        self.disconnect_client = True

    def ftp_SYST(self):
        """Return system type (always returns UNIX type: L8)."""
        # This command is used to find out the type of operating system
        # at the server.  The reply shall have as its first word one of
        # the system names listed in RFC-943.
        # Since that we always return a "/bin/ls -lA"-like output on
        # LIST we  prefer to respond as if we would on Unix in any case.
        if not self.config.device_type:
            self.respond(b'215 UNIX Type: L8')
        else:
            self.respond(b'215 %a ' % self.config.device_type)

    def ftp_USER(self, arg):
        """
        USER FTP command. If the user is already logged in, return 530 else 331 for the PASS command
        :param arg: username specified by the client/attacker
        """
        # first we need to check if the user is authenticated?
        if self.authenticated:
            self.respond(b'530 Cannot switch to another user.')
        else:
            self.username = arg
            self.respond(b'331 Now specify the Password.')

    def ftp_PASS(self, arg):
        if self.authenticated:
            self.respond(b"503 User already authenticated.")
            return
        if not self.username:
            self.respond(b"503 Login with USER first.")
            return
        if self.authentication_ok(user_pass=arg):
            self.respond(b'230 Log in Successful.')
            return
        else:
            self.invalid_login_attempt += 1
            self.respond(b'530 Authentication Failed.')
            return

    # - depreciated/alias commands

    # RFC-1123 requires that the server treat XCUP, XCWD, XMKD, XPWD and XRMD commands as synonyms for CDUP, CWD, MKD,
    # LIST and RMD. Such commands are obsoleted but some ftp clients (e.g. Windows ftp.exe) still use them.

    def ftp_XCUP(self, arg):
        """Change to the parent directory. Synonym for CDUP. Deprecated."""
        return self.ftp_CDUP(arg)

    def ftp_XCWD(self, arg):
        """Change the current working directory. Synonym for CWD. Deprecated."""
        return self.ftp_CWD(arg)

    def ftp_XMKD(self, arg):
        """Create the specified directory. Synonym for MKD. Deprecated."""
        return self.ftp_MKD(arg)

    def ftp_XPWD(self, arg):
        """Return the current working directory. Synonym for PWD. Deprecated."""
        return self.ftp_PWD(arg)

    def ftp_XRMD(self, arg):
        """Remove the specified directory. Synonym for RMD. Deprecated."""
        return self.ftp_RMD(arg)

    def ftp_BYE(self, arg):
        """Quit and end the current ftp session. Synonym for QUIT"""
        return self.ftp_QUIT(arg)


class FTPDataTransferChannel(object):
    """
        Class handling server-data-transfer-process (server-DTP), see RFC-959. Managing data-transfer operations
        involving sending and receiving data.  Used for PORT and PASV commands
          - If mode is Active: tries to connect to connect to remote client and dispatches the resulting connection
          - IF mode is passive: starts a gevent.StreamServer on a known port, for client to connect.
    """
    pass
