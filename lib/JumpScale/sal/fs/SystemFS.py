import sys
import os
import os.path
import hashlib
import re
import logging
import fnmatch
import time
import shutil
import errno
import tempfile
import codecs
import pickle as pickle
import stat
from stat import ST_MTIME
from JumpScale.sal.fs.SystemFSWalker import *


# We import only jumpscale as the j.sal.fs is used before jumpscale is
# initialized. Thus the q cannot be imported yet


from JumpScale import j
# import JumpScale.baselib.codetools #requirement for parsePath
# from text import Text

logger = j.logger.get()

toStr = j.data.text.toStr

# from JumpScale.core.decorators import deprecated

# We do not use the j.core.platformtype here nor do we import the PlatformType as this would
# lead to circular imports and raise an exception
if not sys.platform.startswith('win'):
    try:
        import fcntl
    except ImportError:
        pass

_LOCKDICTIONARY = dict()


class LockException(Exception):

    def __init__(self, message='Failed to get lock', innerException=None):
        if innerException:
            message += '\nProblem caused by:\n%s' % innerException
        Exception.__init__(self, message)
        self.innerException = innerException


class LockTimeoutException(LockException):

    def __init__(self, message='Lock request timed out', innerException=None):
        LockException.__init__(self, message, innerException)


class Exceptions:
    LockException = LockException
    LockTimeoutException = LockTimeoutException


def cleanupString(string, replacewith="_", regex="([^A-Za-z0-9])"):
    '''Remove all non-numeric or alphanumeric characters'''
    # Please don't use the logging system here. The logging system
    # needs this method, using the logging system here would
    # introduce a circular dependency. Be careful not to call other
    # functions that use the logging system.
    return re.sub(regex, replacewith, string)


def lock(lockname, locktimeout=60, reentry=False):
    '''Take a system-wide interprocess exclusive lock. Default timeout is 60 seconds'''
    logger.debug('Lock with name: %s' % lockname)
    try:
        result = lock_(lockname, locktimeout, reentry)
    except Exception as e:
        raise LockException(innerException=e)
    else:
        if not result:
            raise LockTimeoutException(
                message="Cannot acquire lock [%s]" % (lockname))
        else:
            return result


def lock_(lockname, locktimeout=60, reentry=False):
    '''Take a system-wide interprocess exclusive lock.

    Works similar to j.sal.fs.lock but uses return values to denote lock
    success instead of raising fatal errors.

    This refactoring was mainly done to make the lock implementation easier
    to unit-test.
    '''
    # TODO This no longer uses fnctl on Unix, why?
    LOCKPATH = os.path.join(j.dirs.TMPDIR, 'locks')
    lockfile = os.path.join(LOCKPATH, cleanupString(lockname))
    if reentry:
        _LOCKDICTIONARY[lockname] = _LOCKDICTIONARY.setdefault(lockname, 0) + 1

    if not islocked(lockname, reentry=reentry):
        if not j.sal.fs.exists(LOCKPATH):
            j.sal.fs.createDir(LOCKPATH)

        j.sal.fs.writeFile(lockfile, str(os.getpid()))
        return True
    else:
        locked = False
        for i in range(locktimeout + 1):
            locked = islocked(lockname, reentry)
            if not locked:
                break
            else:
                time.sleep(1)

        if not locked:
            return lock_(lockname, locktimeout, reentry)
        else:
            return False


def islocked(lockname, reentry=False):
    '''Check if a system-wide interprocess exclusive lock is set'''
    isLocked = True
    LOCKPATH = os.path.join(j.dirs.TMPDIR, 'locks')
    lockfile = os.path.join(LOCKPATH, cleanupString(lockname))

    try:
        # read the pid from the lockfile
        if j.sal.fs.exists(lockfile):
            pid = open(lockfile, 'rb').read()
        else:
            return False

    except (OSError, IOError) as e:
        # failed to read the lockfile
        if e.errno != errno.ENOENT:  # exception is not 'file or directory not found' -> file probably locked
            raise
    else:
        # open succeeded without exceptions, continue
        # check if a process with pid is still running
        if pid and pid.isdigit():
            pid = int(pid)
            if reentry and pid == os.getpid():
                return False
        if j.sal.fs.exists(lockfile) and (not pid or not j.sal.process.isPidAlive(pid)):
            # cleanup system, pid not active, remove the lockfile
            j.sal.fs.remove(lockfile)
            isLocked = False
    return isLocked


def unlock(lockname):
    """Unlock system-wide interprocess lock"""
    logger.debug('Unlock with name: %s' % lockname)
    try:
        unlock_(lockname)
    except Exception as msg:
        raise j.exceptions.RuntimeError(
            "Cannot unlock [%s] with ERROR: %s" % (lockname, str(msg)))


def unlock_(lockname):
    '''Unlock system-wide interprocess lock

    Works similar to j.sal.fs.unlock but uses return values to denote unlock
    success instead of raising fatal errors.

    This refactoring was mainly done to make the lock implementation easier
    to unit-test.
    '''
    LOCKPATH = os.path.join(j.dirs.TMPDIR, 'locks')
    lockfile = os.path.join(LOCKPATH, cleanupString(lockname))
    if lockname in _LOCKDICTIONARY:
        _LOCKDICTIONARY[lockname] -= 1
        if _LOCKDICTIONARY[lockname] > 0:
            return

    # read the pid from the lockfile
    if j.sal.fs.exists(lockfile):
        try:
            pid = open(lockfile, 'rb').read()
        except:
            return
        if int(pid) != os.getpid():
            j.errorconditionhandler.raiseWarning(
                "Lock %r not owned by this process" % lockname)
            return

        j.sal.fs.remove(lockfile)
    # else:
    #     j.tools.console.echo("Lock %r not found"%lockname)


class FileLock:

    '''Context manager for file-based locks

    Context managers were introduced in Python 2.5, see the documentation on the
    'with' statement for more information:

     * http://www.python.org/dev/peps/pep-0343/
     * http://pyref.infogami.com/with

    @see: L{lock}
    @see: L{unlock}
    '''

    def __init__(self, lock_name, reentry=False, locktimeout=60):
        self.lock_name = lock_name
        self.reentry = reentry
        self.locktimeout = locktimeout

    def __enter__(self):
        lock(self.lock_name, reentry=self.reentry, locktimeout=self.locktimeout)

    def __exit__(self, *exc_info):
        unlock(self.lock_name)

    def __call__(self, func):
        def wrapper(*args, **kwargs):
            lock(self.lock_name, reentry=self.reentry, locktimeout=self.locktimeout)
            try:
                return func(*args, **kwargs)
            finally:
                unlock(self.lock_name)

        return wrapper


class SystemFS:
    exceptions = Exceptions

    def __init__(self):
        self.__jslocation__ = "j.sal.fs"
        self.logger = logger
        self.walker = SystemFSWalker()

    def copyFile(self, fileFrom, to, createDirIfNeeded=False, overwriteFile=True):
        """Copy file

        Copies the file from C{fileFrom} to the file or directory C{to}.
        If C{to} is a directory, a file with the same basename as C{fileFrom} is
        created (or overwritten) in the directory specified.
        Permission bits are copied.

        @param fileFrom: Source file path name
        @type fileFrom: string
        @param to: Destination file or folder path name
        @type to: string

        @autocomplete

        """

        if ((fileFrom is None) or (to is None)):
            raise TypeError(
                "No parameters given to system.fs.copyFile from %s, to %s" % (fileFrom, to))
        if j.sal.fs.isFile(fileFrom):
            # Create target folder first, otherwise copy fails
            target_folder = os.path.dirname(to)
            if createDirIfNeeded:
                self.createDir(target_folder)
            if overwriteFile is False:
                if self.exists(to) and os.path.samefile(to, target_folder):
                    destfilename = os.path.join(to, os.path.basename(fileFrom))
                    if self.exists(destfilename):
                        return
                elif self.exists(to):
                    return
            elif self.isFile(to):
                # overwriting some open  files is frustrating and may not work
                # due to locking [delete/copy is a better strategy]
                self.remove(to)
            try:
                shutil.copy(fileFrom, to)
                self.logger.silly("Copied file from %s to %s" % (fileFrom, to))
            except Exception as e:
                raise j.exceptions.RuntimeError(
                    "Could not copy file from %s to %s, error %s" % (fileFrom, to, e))
        else:
            raise j.exceptions.RuntimeError(
                "Can not copy file, file: %s does not exist in system.fs.copyFile" % (fileFrom))

    def moveFile(self, source, destin):
        """Move a  File from source path to destination path
        @param source: string (Source file path)
        @param destination: string (Destination path the file should be moved to )
        """
        self.logger.silly('Move file from %s to %s' % (source, destin))
        if ((source is None) or (destin is None)):
            raise TypeError(
                "Not enough parameters given to system.fs.moveFile: move from %s, to %s" % (source, destin))
        if not j.sal.fs.isFile(source):
            raise j.exceptions.RuntimeError(
                "The specified source path in system.fs.moveFile does not exist or is no file: %s" % source)
        try:
            self.move(source, destin)
        except Exception as e:
            raise j.exceptions.RuntimeError(
                "File could not be moved...in system.fs.moveFile: from %s to %s , Error %s" % (source, destin, str(e)))

    def renameFile(self, filePath, new_name):
        """
        OBSOLETE
        """
        self.logger.silly("WARNING: renameFIle should not be used")
        return self.move(filePath, new_name)

    def removeIrrelevantFiles(self, path, followSymlinks=True):
        ext = ["pyc", "bak"]
        for path in self.listFilesInDir(path, recursive=True, followSymlinks=followSymlinks):
            if self.getFileExtension(path) in ext:
                self.remove(path)

    def remove(self, path):
        """Remove a File
        @param path: string (File path required to be removed
        """
        self.logger.silly('Remove file with path: %s' % path)
        if len(path) > 0 and path[-1] == os.sep:
            path = path[:-1]
        if path is None:
            raise TypeError(
                'Not enough parameters passed to system.fs.removeFile: %s' % path)
        if os.path.islink(path):
            os.unlink(path)
        if self.exists(path):
            try:
                os.remove(path)
            except Exception as e:
                raise j.exceptions.RuntimeError(
                    "File with path: %s could not be removed\nDetails: %s\n%s" % (path, e, sys.exc_info()[0]))
            self.logger.silly('Done removing file with path: %s' % path)

    def createEmptyFile(self, filename):
        """Create an empty file
        @param filename: string (file path name to be created)
        """
        self.logger.silly(
            'creating an empty file with name & path: %s' % filename)
        if filename is None:
            raise ArithmeticError(
                'Not enough parameters passed to system.fs.createEmptyFile: %s' % filename)
        try:
            open(filename, "w").close()
            self.logger.silly(
                'Empty file %s has been successfully created' % filename)
        except Exception:
            raise j.exceptions.RuntimeError(
                "Failed to create an empty file with the specified filename: %s" % filename)

    def createDir(self, newdir,unlink=True):
        """Create new Directory
        @param newdir: string (Directory path/name)
        if newdir was only given as a directory name, the new directory will be created on the default path,
        if newdir was given as a complete path with the directory name, the new directory will be created in the specified path
        """
        if newdir.find("file://") != -1:
            raise j.exceptions.RuntimeError("Cannot use file notation here")
        self.logger.silly(
            'Creating directory if not exists %s' % toStr(newdir))

        if newdir == '' or newdir is None:
            raise TypeError(
                'The newdir-parameter of system.fs.createDir() is None or an empty string.')

        if self.isLink(newdir) and unlink:
            self.unlink(newdir)

        if self.isDir(newdir):
            self.logger.silly(
                'Directory trying to create: [%s] already exists' % toStr(newdir))
        else:
            head, tail = os.path.split(newdir)
            if head and not j.sal.fs.isDir(head):
                self.createDir(head,unlink=False)
            if tail:
                try:
                    os.mkdir(newdir)
                    # print "mkdir:%s"%newdir
                except OSError as e:
                    if e.errno != os.errno.EEXIST:  # File exists
                        raise

            self.logger.silly('Created the directory [%s]' % toStr(newdir))

    def copyDirTree(self, src, dst, keepsymlinks=False, deletefirst=False,
                    overwriteFiles=True, ignoredir=[".egg-info", ".dist-info"], ignorefiles=[".egg-info"], rsync=True,
                    ssh=False, sshport=22, recursive=True, rsyncdelete=True, createdir=False, applyHrdOnDestPaths=None):
        """Recursively copy an entire directory tree rooted at src.
        The dst directory may already exist; if not,
        it will be created as well as missing parent directories
        @param src: string (source of directory tree to be copied)
        @param rsyncdelete will remove files on dest which are not on source (default)
        @param dst: string (path directory to be copied to...should not already exist)
        @param keepsymlinks: bool (True keeps symlinks instead of copying the content of the file)
        @param deletefirst: bool (Set to True if you want to erase destination first, be carefull, this can erase directories)
        @param overwriteFiles: if True will overwrite files, otherwise will not overwrite when destination exists
        """
        if not ssh:
            if src.find("file://") != -1 or dst.find("file://") != -1:
                raise j.exceptions.RuntimeError(
                    "Cannot use file notation here")

            self.logger.silly('Copy directory tree from %s to %s' % (src, dst))
            if ((src is None) or (dst is None)):
                raise TypeError(
                    'Not enough parameters passed in system.fs.copyDirTree to copy directory from %s to %s ' % (src, dst))
            if j.sal.fs.isDir(src):
                names = os.listdir(src)

                if not j.sal.fs.exists(dst):
                    self.createDir(dst)

                errors = []
                for name in names:
                    # is only for the name
                    if applyHrdOnDestPaths is not None:
                        name2 = applyHrdOnDestPaths.applyOnContent(name)
                    else:
                        name2 = name

                    srcname = j.sal.fs.joinPaths(src, name)
                    dstname = j.sal.fs.joinPaths(dst, name2)
                    if deletefirst and self.exists(dstname):
                        if self.isDir(dstname, False):
                            self.removeDirTree(dstname)
                        if self.isLink(dstname):
                            self.unlink(dstname)

                    if keepsymlinks and j.sal.fs.isLink(srcname):
                        linkto = j.sal.fs.readLink(srcname)
                        j.sal.fs.symlink(linkto, dstname, overwriteFiles)
                    elif j.sal.fs.isDir(srcname):
                        # print "1:%s %s"%(srcname,dstname)
                        j.sal.fs.copyDirTree(srcname, dstname, keepsymlinks, deletefirst,
                                             overwriteFiles=overwriteFiles, applyHrdOnDestPaths=applyHrdOnDestPaths)
                    else:
                        # print "2:%s %s"%(srcname,dstname)
                        self.copyFile(
                            srcname, dstname, createDirIfNeeded=False, overwriteFile=overwriteFiles)
            else:
                raise j.exceptions.RuntimeError(
                    'Source path %s in system.fs.copyDirTree is not a directory' % src)
        else:
            # didnt use j.sal.rsync because its not complete and doesnt work
            # properly
            excl = ""
            for item in ignoredir:
                excl += "--exclude '*%s*/' " % item
            for item in ignorefiles:
                excl += "--exclude '*%s*' " % item
            excl += "--exclude '*.pyc' "
            excl += "--exclude '*.bak' "
            excl += "--exclude '*__pycache__*' "

            if self.isDir(src):
                if dst[-1] != "/":
                    dst += "/"
                if src[-1] != "/":
                    src += "/"

            dstpath = dst.split(':')[1] if ':' in dst else dst
            cmd = "rsync "
            if keepsymlinks:
                #-l is keep symlinks, -L follow
                cmd += " -rlptgo --partial %s" % excl
            else:
                cmd += " -rLptgo --partial %s" % excl
            if not recursive:
                cmd += " --exclude \"*/\""
            if rsyncdelete:
                cmd += " --delete"
            if ssh:
                cmd += " -e 'ssh -o StrictHostKeyChecking=no -p %s' " % sshport
            if createdir:
                cmd += "--rsync-path='mkdir -p %s && rsync' " % self.getParent(
                    dstpath)
            cmd += " '%s' '%s'" % (src, dst)
            print(cmd)

            return j.tools.cuisine.local.core.run(cmd)[1]

    def removeDirTree(self, path, onlyLogWarningOnRemoveError=False):
        """Recursively delete a directory tree.
            @param path: the path to be removed
        """
        if path is None:
            raise ValueError('Path is None in system.fs.removeDir')
        self.logger.silly('Removing directory tree with path: %s' % path)
        if self.isLink(path):
            self.remove(path)
        if self.isFile(path):
            self.remove(path)

        if(j.sal.fs.exists(path)):
            if(self.isDir(path)):
                if onlyLogWarningOnRemoveError:
                    def errorHandler(shutilFunc, shutilPath, shutilExc_info):
                        self.logger.silly(
                            'WARNING: could not remove %s while recursively deleting %s' % (shutilPath, path))
                    self.logger.silly(
                        'Trying to remove Directory tree with path: %s (warn on errors)' % path)
                    shutil.rmtree(path, onerror=errorHandler)
                else:
                    self.logger.silly(
                        'Trying to remove Directory tree with path: %s' % path)
                    shutil.rmtree(path)

                self.logger.silly(
                    'Directory tree with path: %s is successfully removed' % path)
            else:
                raise ValueError(
                    "Specified path: %s is not a Directory in system.fs.removeDirTree" % path)

    def removeDir(self, path):
        """Remove a Directory
        @param path: string (Directory path that should be removed)
        """
        self.logger.silly('Removing the directory with path: %s' % path)
        if path is None:
            raise TypeError('Path is None in system.fs.removeDir')
        if(j.sal.fs.exists(path)):
            if(j.sal.fs.isDir(path)):
                os.rmdir(path)
                self.logger.silly(
                    'Directory with path: %s is successfully removed' % path)
            else:
                raise ValueError(
                    "Path: %s is not a Directory in system.fs.removeDir" % path)
        else:
            raise j.exceptions.RuntimeError(
                "Path: %s does not exist in system.fs.removeDir" % path)

    def changeDir(self, path):
        """Changes Current Directory
        @param path: string (Directory path to be changed to)
        """
        self.logger.silly('Changing directory to: %s' % path)
        if path is None:
            raise TypeError('Path is not given in system.fs.changeDir')
        if(j.sal.fs.exists(path)):
            if(j.sal.fs.isDir(path)):
                os.chdir(path)
                newcurrentPath = os.getcwd()
                self.logger.silly(
                    'Directory successfully changed to %s' % path)
                return newcurrentPath
            else:
                raise ValueError(
                    "Path: %s in system.fs.changeDir is not a Directory" % path)
        else:
            raise j.exceptions.RuntimeError(
                "Path: %s in system.fs.changeDir does not exist" % path)

    def moveDir(self, source, destin):
        """Move Directory from source to destination
        @param source: string (Source path where the directory should be removed from)
        @param destin: string (Destination path where the directory should be moved into)
        """
        self.logger.silly('Moving directory from %s to %s' % (source, destin))
        if ((source is None) or (destin is None)):
            raise TypeError(
                'Not enough passed parameters to moveDirectory from %s to %s in system.fs.moveDir ' % (source, destin))
        if(j.sal.fs.isDir(source)):
            j.sal.fs.move(source, destin)
            self.logger.silly(
                'Directory is successfully moved from %s to %s' % (source, destin))
        else:
            raise j.exceptions.RuntimeError(
                "Specified Source path: %s does not exist in system.fs.moveDir" % source)

    def joinPaths(self, *args):
        """Join one or more path components.
        If any component is an absolute path, all previous components are thrown away, and joining continues.
        @param path1: string
        @param path2: string
        @param path3: string
        @param .... : string
        @rtype: Concatenation of path1, and optionally path2, etc...,
        with exactly one directory separator (os.sep) inserted between components, unless path2 is empty.
        """
        args = [toStr(x) for x in args]
        self.logger.silly('Join paths %s' % (str(args)))
        if args is None:
            raise TypeError('Not enough parameters %s' % (str(args)))
        if os.sys.platform.startswith("win"):
            args2 = []
            for item in args:
                item = item.replace("/", "\\")
                while len(item) > 0 and item[0] == "\\":
                    item = item[1:]
                args2.append(item)
            args = args2
        try:
            return os.path.join(*args)
        except Exception as e:
            raise j.exceptions.RuntimeError(
                "Failed to join paths: %s, Error %s " % (str(args), str(e)))

    def getDirName(self, path, lastOnly=False, levelsUp=None):
        """
        Return a directory name from pathname path.
        @param path the path to find a directory within
        @param lastOnly means only the last part of the path which is a dir (overrides levelsUp to 0)
        @param levelsUp means, return the parent dir levelsUp levels up
         e.g. ...getDirName("/opt/qbase/bin/something/test.py", levelsUp=0) would return something
         e.g. ...getDirName("/opt/qbase/bin/something/test.py", levelsUp=1) would return bin
         e.g. ...getDirName("/opt/qbase/bin/something/test.py", levelsUp=10) would raise an error
        """
        self.logger.silly('Get directory name of path: %s' % path)
        if path is None:
            raise TypeError('Path is not passed in system.fs.getDirName')
        dname = os.path.dirname(path)
        dname = dname.replace("/", os.sep)
        dname = dname.replace("//", os.sep)
        dname = dname.replace("\\", os.sep)
        if lastOnly:
            dname = dname.split(os.sep)[-1]
            return dname
        if levelsUp is not None:
            parts = dname.split(os.sep)
            if len(parts) - levelsUp > 0:
                return parts[len(parts) - levelsUp - 1]
            else:
                raise j.exceptions.RuntimeError(
                    "Cannot find part of dir %s levels up, path %s is not long enough" % (levelsUp, path))
        return dname + os.sep if dname else dname

    def getBaseName(self, path):
        """Return the base name of pathname path."""
        self.logger.silly('Get basename for path: %s' % path)
        if path is None:
            raise TypeError('Path is not passed in system.fs.getDirName')
        try:
            return os.path.basename(path.rstrip(os.path.sep))
        except Exception as e:
            raise j.exceptions.RuntimeError(
                'Failed to get base name of the given path: %s, Error: %s' % (path, str(e)))

    def pathShorten(self, path):
        """
        Clean path (change /var/www/../lib to /var/lib). On Windows, if the
        path exists, the short path name is returned.

        @param path: Path to clean
        @type path: string
        @return: Cleaned (short) path
        @rtype: string
        """
        cleanedPath = os.path.normpath(path)
        if j.core.platformtype.myplatform.isWindows() and self.exists(cleanedPath):
            # Only execute on existing paths, otherwise an error will be raised
            import win32api
            cleanedPath = win32api.GetShortPathName(cleanedPath)
            # Re-add '\' if original path had one
            sep = os.path.sep
            if path and path[-1] == sep and cleanedPath[-1] != sep:
                cleanedPath = "%s%s" % (cleanedPath, sep)
        return cleanedPath

    def pathClean(self, path):
        """
        goal is to get a equal representation in / & \ in relation to os.sep
        """
        path = path.replace("/", os.sep)
        path = path.replace("//", os.sep)
        path = path.replace("\\", os.sep)
        path = path.replace("\\\\", os.sep)
        # path=self.pathNormalize(path)
        path = path.strip()
        return path

    def pathDirClean(self, path):
        path = path + os.sep
        return self.pathClean(path)

    def dirEqual(self, path1, path2):
        return self.pathDirClean(path1) == self.pathDirClean(path2)

    def pathNormalize(self, path, root=""):
        """
        paths are made absolute & made sure they are in line with os.sep
        @param path: path to normalize
        @root is std the application you are in, can overrule
        """
        if root == "":
            root = self.getcwd()
        path = self.pathClean(path)
        if len(path) > 0 and path[0] != os.sep:
            path = self.joinPaths(root, path)
        return path

    def pathRemoveDirPart(self, path, toremove, removeTrailingSlash=False):
        """
        goal remove dirparts of a dirpath e,g, a basepath which is not needed
        will look for part to remove in full path but only full dirs
        """
        path = self.pathNormalize(path)
        toremove = self.pathNormalize(toremove)

        if self.pathClean(toremove) == self.pathClean(path):
            return ""
        path = self.pathClean(path)
        path = path.replace(self.pathDirClean(toremove), "")
        if removeTrailingSlash:
            if len(path) > 0 and path[0] == os.sep:
                path = path[1:]
        path = self.pathClean(path)
        return path

    def processPathForDoubleDots(self, path):
        """
        /root/somepath/.. would become /root
        /root/../somepath/ would become /somepath

        result will always be with / slashes
        """
        # print "processPathForDoubleDots:%s"%path
        path = self.pathClean(path)
        path = path.replace("\\", "/")
        result = []
        for item in path.split("/"):
            if item == "..":
                if result == []:
                    raise j.exceptions.RuntimeError(
                        "Cannot processPathForDoubleDots for paths with only ..")
                else:
                    result.pop()
            else:
                result.append(item)
        return "/".join(result)

    def getParent(self, path):
        """
        Returns the parent of the path:
        /dir1/dir2/file_or_dir -> /dir1/dir2/
        /dir1/dir2/            -> /dir1/
        """
        parts = path.split(os.sep)
        if parts[-1] == '':
            parts = parts[:-1]
        parts = parts[:-1]
        if parts == ['']:
            return os.sep
        return os.sep.join(parts)

    def getFileExtension(self, path):
        ext = os.path.splitext(path)[1]
        return ext.strip('.')

    def chown(self, path, user, group=None):
        from pwd import getpwnam
        from grp import getgrnam
        getpwnam(user)[2]
        uid = getpwnam(user).pw_uid
        if group is not None:
            gid = getgrnam(group).gr_gid
        else:
            gid = getpwnam(user).pw_gid
        os.chown(path, uid, gid)
        for root, dirs, files in os.walk(path):
            for ddir in dirs:
                path = os.path.join(root, ddir)
                try:
                    os.chown(path, uid, gid)
                except Exception as e:
                    if str(e).find("No such file or directory") == -1:
                        raise j.exceptions.RuntimeError("%s" % e)
            for file in files:
                path = os.path.join(root, file)
                try:
                    os.chown(path, uid, gid)
                except Exception as e:
                    if str(e).find("No such file or directory") == -1:
                        raise j.exceptions.RuntimeError("%s" % e)

    def chmod(self, path, permissions):
        """
        @param permissions e.g. 0o660 (USE OCTAL !!!)
        """
        os.chmod(path, permissions)
        for root, dirs, files in os.walk(path):
            for ddir in dirs:
                path = os.path.join(root, ddir)
                try:
                    os.chmod(path, permissions)
                except Exception as e:
                    if str(e).find("No such file or directory") == -1:
                        raise j.exceptions.RuntimeError("%s" % e)

            for file in files:
                path = os.path.join(root, file)
                try:
                    os.chmod(path, permissions)
                except Exception as e:
                    if str(e).find("No such file or directory") == -1:
                        raise j.exceptions.RuntimeError("%s" % e)

    def parsePath(self, path, baseDir="", existCheck=True, checkIsFile=False):
        """
        parse paths of form /root/tmp/33_adoc.doc into the path, priority which is numbers before _ at beginning of path
        also returns filename
        checks if path can be found, if not will fail
        when filename="" then is directory which has been parsed
        if basedir specified that part of path will be removed

        example:
        j.sal.fs.parsePath("/opt/qbase3/apps/specs/myspecs/definitions/cloud/datacenter.txt","/opt/qbase3/apps/specs/myspecs/",existCheck=False)
        @param path is existing path to a file
        @param baseDir, is the absolute part of the path not required
        @return list of dirpath,filename,extension,priority
             priority = 0 if not specified
        """
        # make sure only clean path is left and the filename is out
        if existCheck and not self.exists(path):
            raise j.exceptions.RuntimeError(
                "Cannot find file %s when importing" % path)
        if checkIsFile and not self.isFile(path):
            raise j.exceptions.RuntimeError(
                "Path %s should be a file (not e.g. a dir), error when importing" % path)
        extension = ""
        if self.isDir(path):
            name = ""
            path = self.pathClean(path)
        else:
            name = self.getBaseName(path)
            path = self.pathClean(path)
            # make sure only clean path is left and the filename is out
            path = self.getDirName(path)
            # find extension
            regexToFindExt = "\.\w*$"
            if j.tools.code.regex.match(regexToFindExt, name):
                extension = j.tools.code.regex.findOne(
                    regexToFindExt, name).replace(".", "")
                # remove extension from name
                name = j.tools.code.regex.replace(
                    regexToFindExt, regexFindsubsetToReplace=regexToFindExt, replaceWith="", text=name)

        if baseDir != "":
            path = self.pathRemoveDirPart(path, baseDir)

        if name == "":
            dirOrFilename = j.sal.fs.getDirName(path, lastOnly=True)
        else:
            dirOrFilename = name
        # check for priority
        regexToFindPriority = "^\d*_"
        if j.tools.code.regex.match(regexToFindPriority, dirOrFilename):
            # found priority in path
            priority = j.tools.code.regex.findOne(
                regexToFindPriority, dirOrFilename).replace("_", "")
            # remove priority from path
            name = j.tools.code.regex.replace(
                regexToFindPriority, regexFindsubsetToReplace=regexToFindPriority, replaceWith="", text=name)
        else:
            priority = 0

        return path, name, extension, priority  # if name =="" then is dir

    def getcwd(self):
        """get current working directory
        @rtype: string (current working directory path)
        """
        self.logger.silly('Get current working directory')
        try:
            return os.getcwd()
        except Exception as e:
            raise j.exceptions.RuntimeError(
                'Failed to get current working directory')

    def readLink(self, path, absolute=True):
        """Works only for unix
        Return a string representing the path to which the symbolic link points.
        @param absolute, if True then look for absolute source location
        returns the source location
        """
        while path[-1] == "/" or path[-1] == "\\":
            path = path[:-1]
        self.logger.silly('Read link with path: %s' % path)
        if path is None:
            raise TypeError('Path is not passed in system.fs.readLink')
        if j.core.platformtype.myplatform.isUnix():
            try:
                res = os.readlink(path)
            except Exception as e:
                raise j.exceptions.RuntimeError(
                    'Failed to read link with path: %s \nERROR: %s' % (path, str(e)))
        elif j.core.platformtype.myplatform.isWindows():
            raise j.exceptions.RuntimeError('Cannot readLink on windows')

        if res.startswith("..") and absolute:
            if self.isFile(path):
                srcDir = self.getParent(self.getDirName(path))
            else:
                srcDir = self.getDirName(path)
            path2 = self.joinPaths(srcDir, res)
            res = os.path.abspath(path2)

        return res

    def removeLinks(self, path):
        """
        find all links & remove
        """
        if not self.exists(path):
            return
        items = self._listAllInDir(
            path=path, recursive=True, followSymlinks=False, listSymlinks=True)
        items = [item for item in items[0] if j.sal.fs.isLink(item)]
        for item in items:
            j.sal.fs.unlink(item)

    def _listInDir(self, path, followSymlinks=True):
        """returns array with dirs & files in directory
        @param path: string (Directory path to list contents under)
        """
        if path is None:
            raise TypeError('Path is not passed in system.fs.listDir')
        if(j.sal.fs.exists(path)):
            if self.isDir(path, followSymlinks):
                names = os.listdir(path)
                return names
            else:
                raise ValueError(
                    "Specified path: %s is not a Directory in system.fs.listDir" % path)
        else:
            raise j.exceptions.RuntimeError(
                "Specified path: %s does not exist in system.fs.listDir" % path)

    def listFilesInDir(self, path, recursive=False, filter=None, minmtime=None, maxmtime=None,
                       depth=None, case_sensitivity='os', exclude=[], followSymlinks=True, listSymlinks=False):
        """Retrieves list of files found in the specified directory
        @param path:       directory path to search in
        @type  path:       string
        @param recursive:  recursively look in all subdirs
        @type  recursive:  boolean
        @param filter:     unix-style wildcard (e.g. *.py) - this is not a regular expression
        @type  filter:     string
        @param minmtime:   if not None, only return files whose last modification time > minmtime (epoch in seconds)
        @type  minmtime:   integer
        @param maxmtime:   if not None, only return files whose last modification time < maxmtime (epoch in seconds)
        @Param depth: is levels deep wich we need to go
        @type  maxmtime:   integer
        @Param exclude: list of std filters if matches then exclude
        @rtype: list
        """
        if depth is not None:
            depth = int(depth)
        self.logger.silly('List files in directory with path: %s' % path)
        if depth == 0:
            depth = None
        # if depth is not None:
        #     depth+=1
        filesreturn, depth = self._listAllInDir(path, recursive, filter, minmtime, maxmtime, depth, type="f", case_sensitivity=case_sensitivity,
                                                exclude=exclude, followSymlinks=followSymlinks, listSymlinks=listSymlinks)
        return filesreturn

    def listFilesAndDirsInDir(self, path, recursive=False, filter=None, minmtime=None,
                              maxmtime=None, depth=None, type="fd", followSymlinks=True, listSymlinks=False):
        """Retrieves list of files found in the specified directory
        @param path:       directory path to search in
        @type  path:       string
        @param recursive:  recursively look in all subdirs
        @type  recursive:  boolean
        @param filter:     unix-style wildcard (e.g. *.py) - this is not a regular expression
        @type  filter:     string
        @param minmtime:   if not None, only return files whose last modification time > minmtime (epoch in seconds)
        @type  minmtime:   integer
        @param maxmtime:   if not None, only return files whose last modification time < maxmtime (epoch in seconds)
        @Param depth: is levels deep wich we need to go
        @type  maxmtime:   integer
        @param type is string with f & d inside (f for when to find files, d for when to find dirs)
        @rtype: list
        """
        if depth is not None:
            depth = int(depth)
        self.logger.silly('List files in directory with path: %s' % path)
        if depth == 0:
            depth = None
        # if depth is not None:
        #     depth+=1
        filesreturn, depth = self._listAllInDir(
            path, recursive, filter, minmtime, maxmtime, depth, type=type, followSymlinks=followSymlinks, listSymlinks=listSymlinks)
        return filesreturn

    def _listAllInDir(self, path, recursive, filter=None, minmtime=None, maxmtime=None, depth=None,
                      type="df", case_sensitivity='os', exclude=[], followSymlinks=True, listSymlinks=True):
        """
        # There are 3 possible options for case-sensitivity for file names
        # 1. `os`: the same behavior as the OS
        # 2. `sensitive`: case-sensitive comparison
        # 3. `insensitive`: case-insensitive comparison
        """
        dircontent = self._listInDir(path)
        filesreturn = []

        if case_sensitivity.lower() == 'sensitive':
            matcher = fnmatch.fnmatchcase
        elif case_sensitivity.lower() == 'insensitive':
            def matcher(fname, pattern):
                return fnmatch.fnmatchcase(fname.lower(), pattern.lower())
        else:
            matcher = fnmatch.fnmatch

        for direntry in dircontent:
            fullpath = self.joinPaths(path, direntry)

            # if followSymlinks:
            #     if self.isLink(fullpath):
            #         fullpath=self.readLink(fullpath)

            if self.isFile(fullpath) and "f" in type:
                includeFile = False
                if (filter is None) or matcher(direntry, filter):
                    if (minmtime is not None) or (maxmtime is not None):
                        mymtime = os.stat(fullpath)[ST_MTIME]
                        if (minmtime is None) or (mymtime > minmtime):
                            if (maxmtime is None) or (mymtime < maxmtime):
                                includeFile = True
                    else:
                        includeFile = True
                if includeFile:
                    if exclude != []:
                        for excludeItem in exclude:
                            if matcher(direntry, excludeItem):
                                includeFile = False
                    if includeFile:
                        filesreturn.append(fullpath)
            elif self.isDir(fullpath):
                if "d" in type:
                    # if not(listSymlinks==False and self.isLink(fullpath)):
                    filesreturn.append(fullpath)
                if recursive:
                    if depth is not None and depth != 0:
                        depth = depth - 1
                    if depth is None or depth != 0:
                        exclmatch = False
                        if exclude != []:
                            for excludeItem in exclude:
                                if matcher(fullpath, excludeItem):
                                    exclmatch = True
                        if exclmatch is False:
                            if not(followSymlinks is False and self.isLink(fullpath)):
                                r, depth = self._listAllInDir(fullpath, recursive, filter, minmtime, maxmtime, depth=depth, type=type,
                                                              exclude=exclude, followSymlinks=followSymlinks, listSymlinks=listSymlinks)
                                if len(r) > 0:
                                    filesreturn.extend(r)
            # and followSymlinks==False and listSymlinks:
            elif self.isLink(fullpath) and followSymlinks==False and listSymlinks:
                filesreturn.append(fullpath)

        return filesreturn, depth

    def changeFileNames(self, toReplace, replaceWith, pathToSearchIn,
                        recursive=True, filter=None, minmtime=None, maxmtime=None):
        """
        @param toReplace e.g. {name}
        @param replace with e.g. "jumpscale"
        """
        paths = self.listFilesInDir(
            pathToSearchIn, recursive, filter, minmtime, maxmtime)
        for path in paths:
            path2 = path.replace(toReplace, replaceWith)
            if path2 != path:
                self.renameFile(path, path2)

    def replaceWordsInFiles(self, pathToSearchIn, templateengine, recursive=True,
                            filter=None, minmtime=None, maxmtime=None):
        """
        apply templateengine to list of found files
        @param templateengine =te  #example below
            te=j.tools.code.templateengine.new()
            te.add("name",self.a.name)
            te.add("description",self.ayses.description)
            te.add("version",self.ayses.version)
        """
        paths = self.listFilesInDir(
            pathToSearchIn, recursive, filter, minmtime, maxmtime)
        for path in paths:
            templateengine.replaceInsideFile(path)

    def listDirsInDir(self, path, recursive=False, dirNameOnly=False, findDirectorySymlinks=True, followSymlinks=True):
        """ Retrieves list of directories found in the specified directory
        @param path: string represents directory path to search in
        @rtype: list
        """
        self.logger.silly('List directories in directory with path: %s, recursive = %s' % (
            path, str(recursive)))

        items = self._listInDir(path)
        filesreturn = []
        for item in items:
            fullpath = os.path.join(path, item)
            if self.isDir(fullpath, findDirectorySymlinks):
                if dirNameOnly:
                    filesreturn.append(item)
                else:
                    filesreturn.append(fullpath)
            if recursive and self.isDir(fullpath, followSymlinks):
                if self.isLink(fullpath):
                    fullpath = self.readLink(fullpath)
                filesreturn.extend(self.listDirsInDir(
                    fullpath, recursive=recursive, dirNameOnly=dirNameOnly,
                    findDirectorySymlinks=findDirectorySymlinks, followSymlinks=followSymlinks))
        return filesreturn

    def listPyScriptsInDir(self, path, recursive=True, filter="*.py"):
        """ Retrieves list of python scripts (with extension .py) in the specified directory
        @param path: string represents the directory path to search in
        @rtype: list
        """
        result = []
        for file in j.sal.fs.listFilesInDir(path, recursive=recursive, filter=filter):
            if file.endswith(".py"):
                filename = file.split(os.sep)[-1]
                scriptname = filename.rsplit(".", 1)[0]
                result.append(scriptname)
        return result

    def move(self, source, destin):
        """Main Move function
        @param source: string (If the specified source is a File....Calls moveFile function)
        (If the specified source is a Directory....Calls moveDir function)
        """
        if not j.sal.fs.exists(source):
            raise IOError('%s does not exist' % source)
        shutil.move(source, destin)

    def exists(self, path, followlinks=True):
        """Check if the specified path exists
        @param path: string
        @rtype: boolean (True if path refers to an existing path)
        """
        if path is None:
            raise TypeError('Path is not passed in system.fs.exists')
        if os.path.exists(path) or os.path.islink(path):
            if self.isLink(path) and followlinks:
                self.logger.silly('path %s exists' % str(path.encode("utf-8")))
                relativelink = self.readLink(path)
                newpath = self.joinPaths(self.getParent(path), relativelink)
                return self.exists(newpath)
            else:
                return True
        self.logger.silly('path %s does not exist' % str(path.encode("utf-8")))
        return False

    def symlink(self, path, target, overwriteTarget=False):
        """Create a symbolic link
        @param path: source path desired to create a symbolic link for
        @param target: destination path required to create the symbolic link at
        @param overwriteTarget: boolean indicating whether target can be overwritten
        """
        self.logger.silly(
            'Getting symlink for path: %s to target %s' % (path, target))
        if (path is None):
            raise TypeError('Path is None in system.fs.symlink')

        if target[-1] == "/":
            target = target[:-1]

        if overwriteTarget and (self.exists(target) or self.isLink(target)):
            if self.isLink(target):
                self.unlink(target)
            elif self.isDir(target):
                self.removeDirTree(target)
            else:
                self.remove(target)

        dir = j.sal.fs.getDirName(target)
        if not j.sal.fs.exists(dir):
            j.sal.fs.createDir(dir)

        if j.core.platformtype.myplatform.isUnix():
            self.logger.silly("Creating link from %s to %s" % (path, target))
            os.symlink(path, target)
        elif j.core.platformtype.myplatform.isWindows():
            path = path.replace("+", ":")
            cmd = "junction \"%s\" \"%s\"" % (self.pathNormalize(target).replace(
                "\\", "/"), self.pathNormalize(path).replace("\\", "/"))
            print(cmd)
            j.sal.process.execute(cmd)

    def hardlinkFile(self, source, destin):
        """Create a hard link pointing to source named destin. Availability: Unix.
        @param source: string
        @param destin: string
        @rtype: concatenation of dirname, and optionally linkname, etc.
        with exactly one directory separator (os.sep) inserted between components, unless path2 is empty
        """
        self.logger.silly(
            'Create a hard link pointing to %s named %s' % (source, destin))
        if (source is None):
            raise TypeError(
                'Source path is not passed in system.fs.hardlinkFile')
        try:
            if j.core.platformtype.myplatform.isUnix():
                return os.link(source, destin)
            else:
                raise j.exceptions.RuntimeError(
                    'Cannot create a hard link on windows')
        except:
            raise j.exceptions.RuntimeError(
                'Failed to hardLinkFile from %s to %s' % (source, destin))

    def checkDirParam(self, path):
        if(path.strip() == ""):
            raise TypeError("path parameter cannot be empty.")
        path = path.replace("//", "/")
        path = path.replace("\\\\", "/")
        path = path.replace("\\", "/")
        if path[-1] != "/":
            path = path + "/"
        path = path.replace("/", os.sep)
        return path

    def isDir(self, path, followSoftlink=False):
        """Check if the specified Directory path exists
        @param path: string
        @param followSoftlink: boolean
        @rtype: boolean (True if directory exists)
        """
        if (path is None):
            raise TypeError('Directory path is None in system.fs.isDir')
        if self.isLink(path):
            if not followSoftlink:
                return False
            path = self.readLink(path)
        return os.path.isdir(path)

    def isEmptyDir(self, path):
        """Check if the specified directory path is empty
        @param path: string
        @rtype: boolean (True if directory is empty)
        """
        if (path is None):
            raise TypeError('Directory path is None in system.fs.isEmptyDir')
        try:
            if(self._listInDir(path) == []):
                self.logger.silly('path %s is an empty directory' % path)
                return True
            self.logger.silly('path %s is not an empty directory' % path)
            return False
        except:
            raise j.exceptions.RuntimeError(
                'Failed to check if the specified path: %s is an empty directory...in system.fs.isEmptyDir' % path)

    def isFile(self, path, followSoftlink=True):
        """Check if the specified file exists for the given path
        @param path: string
        @param followSoftlink: boolean
        @rtype: boolean (True if file exists for the given path)
        """
        self.logger.silly("isfile:%s" % path)

        if (path is None):
            raise TypeError('File path is None in system.fs.isFile')
        try:
            if not followSoftlink and self.isLink(path):
                self.logger.silly('path %s is a file' % path)
                return True

            if(os.path.isfile(path)):
                self.logger.silly('path %s is a file' % path)
                return True

            self.logger.silly('path %s is not a file' % path)
            return False
        except:
            raise j.exceptions.RuntimeError(
                'Failed to check if the specified path: %s is a file...in system.fs.isFile' % path)

    def isExecutable(self, path):
        statobj = self.statPath(path, follow_symlinks=False)
        return not (stat.S_IXUSR & statobj.st_mode == 0)

    def isLink(self, path, checkJunction=False):
        """Check if the specified path is a link
        @param path: string
        @rtype: boolean (True if the specified path is a link)
        """
        if path[-1] == os.sep:
            path = path[:-1]
        if (path is None):
            raise TypeError('Link path is None in system.fs.isLink')

        if checkJunction and j.core.platformtype.myplatform.isWindows():
            cmd = "junction %s" % path
            try:
                result = j.sal.process.execute(cmd)
            except Exception as e:
                raise j.exceptions.RuntimeError(
                    "Could not execute junction cmd, is junction installed? Cmd was %s." % cmd)
            if result[0] != 0:
                raise j.exceptions.RuntimeError(
                    "Could not execute junction cmd, is junction installed? Cmd was %s." % cmd)
            if result[1].lower().find("substitute name") != -1:
                return True
            else:
                return False

        if(os.path.islink(path)):
            self.logger.silly('path %s is a link' % path)
            return True
        self.logger.silly('path %s is not a link' % path)
        return False

    def isMount(self, path):
        """Return true if pathname path is a mount point:
        A point in a file system where a different file system has been mounted.
        """
        self.logger.silly('Check if path %s is a mount point' % path)
        if path is None:
            raise TypeError('Path is passed null in system.fs.isMount')
        return os.path.ismount(path)

    def statPath(self, path, follow_symlinks=True):
        """Perform a stat() system call on the given path
        @rtype: object whose attributes correspond to the members of the stat structure
        """
        if path is None:
            raise TypeError('Path is None in system.fs.statPath')
        try:
            return os.stat(path, follow_symlinks=follow_symlinks)
        except:
            raise OSError(
                'Failed to perform stat system call on the specific path: %s in system.fs.statPath' % (path))

    def renameDir(self, dirname, newname, overwrite=False):
        """Rename Directory from dirname to newname
        @param dirname: string (Directory original name)
        @param newname: string (Directory new name to be changed to)
        """
        self.logger.silly('Renaming directory %s to %s' % (dirname, newname))
        if dirname == newname:
            return
        if ((dirname is None) or (newname is None)):
            raise TypeError(
                'Not enough parameters passed to system.fs.renameDir...[%s, %s]' % (dirname, newname))
        if(self.isDir(dirname)):
            if overwrite and self.exists(dirname):
                self.removeDirTree(dirname)
            os.rename(dirname, newname)
        else:
            raise ValueError(
                'Path: %s is not a directory in system.fs.renameDir' % dirname)

    def unlinkFile(self, filename):
        """Remove the file path (only for files, not for symlinks)
        @param filename: File path to be removed
        """
        self.logger.silly('Unlink file with path: %s' % filename)

        if (filename is None):
            raise TypeError('File name is None in QSstem.unlinkFile')
        if not self.isFile(filename):
            raise j.exceptions.RuntimeError(
                "filename is not a file so cannot unlink")
        try:
            os.unlink(filename)
        except:
            raise OSError(
                'Failed to unlink the specified file path: %s in system.fs.unlinkFile' % filename)

    def unlink(self, filename):
        '''Remove the given file if it's a file or a symlink

        @param filename: File path to be removed
        @type filename: string
        '''
        self.logger.silly('Unlink path: %s' % filename)

        if not filename:
            raise TypeError('File name is None in system.fs.unlink')
        try:
            os.unlink(filename)
        except:
            raise OSError(
                'Failed to unlink the specified file path: [%s] in system.ds.unlink' % filename)

    def fileGetContents(self, filename):
        """Read a file and get contents of that file
        @param filename: string (filename to open for reading )
        @rtype: string representing the file contents
        """
        if filename is None:
            raise TypeError('File name is None in system.fs.fileGetContents')
        self.logger.silly('Opened file %s for reading' % filename)
        self.logger.silly('Reading file %s' % filename)
        with open(filename) as fp:
            data = fp.read()
        self.logger.silly('File %s is closed after reading' % filename)
        return data

    def fileGetBinaryContents(self, filename):
        """Read a file in binary mode and get contents of that file
        @param filename: string (filename to open for reading )
        @rtype: string representing the file contents
        """
        if filename is None:
            raise TypeError('File name is None in system.fs.fileGetContents')
        self.logger.silly('Opened file %s for reading' % filename)
        self.logger.silly('Reading file %s' % filename)
        with open(filename, mode='rb') as fp:
            data = fp.read()
        self.logger.silly('File %s is closed after reading' % filename)
        return data

    def readFile(self, filename):
        """
        Get contents as string from filename.

        @param filename str: file path to read from.
        """
        return self.fileGetContents(filename)

    def fileGetUncommentedContents(self, filename):
        """Read a file and get uncommented contents of that file
        @param filename: string (filename to open for reading )
        @rtype: list of lines of uncommented file contents
        """
        if filename is None:
            raise TypeError('File name is None in system.fs.fileGetContents')
        self.logger.silly('Opened file %s for reading' % filename)
        # self.logger.silly('Reading file %s'% filename,9)
        with open(filename) as fp:
            data = fp.readlines()
            uncommented = list()
            for line in data:
                if not line.strip().startswith('#') and not line.startswith('\n'):
                    line = line.replace('\n', '')
                    uncommented.append(line)
            self.logger.silly('File %s is closed after reading' % filename)
            return uncommented

    def fileGetTextContents(self, filename):
        """Read a UTF-8 file and get contents of that file. Takes care of the [BOM](http://en.wikipedia.org/wiki/Byte_order_mark)
        @param filename: string (filename to open for reading)
        @rtype: string representing the file contents
        """
        if filename is None:
            raise TypeError(
                'File name is None in system.fs.fileGetTextContents')
        with open(filename, encoding='utf8') as f:  # enforce utf8 encoding
            s = f.read()

            boms = [codecs.BOM_UTF8]
            for bom in boms:  # we can add more BOMs later:
                if s.startswith(bom.decode()):
                    s = s.replace(bom.decode(), '', 1)
                    break
            return s

    def touch(self, paths, overwrite=True):
        """
        can be single path or multiple (then list)
        """
        if j.data.types.list.check(paths):
            for item in paths:
                self.touch(item, overwrite=overwrite)
        path = paths
        self.createDir(j.sal.fs.getDirName(path))
        if overwrite:
            self.remove(path)
        if not self.exists(path=path):
            self.writeFile(path, "")

    def writeFile(self, filename, contents, append=False):
        """
        Open a file and write file contents, close file afterwards
        @param contents: string (file contents to be written)
        """
        if (filename is None) or (contents is None):
            raise TypeError('Passed None parameters in system.fs.writeFile')
        self.logger.silly('Opened file %s for writing' % filename)
        if append is False:
            fp = open(filename, "wb")
        else:
            fp = open(filename, "ab")
        self.logger.silly('Writing contents in file %s' % filename)
        if j.data.types.string.check(contents):
            fp.write(bytes(contents, 'UTF-8'))
        else:
            fp.write(contents)
        # fp.write(contents)
        fp.close()

    def fileSize(self, filename):
        """Get Filesize of file in bytes
        @param filename: the file u want to know the filesize of
        @return: int representing file size
        """
        self.logger.silly('Getting filesize of file: %s' % filename)
        if not self.exists(filename):
            raise j.exceptions.RuntimeError(
                "Specified file: %s does not exist" % filename)
        try:
            return os.path.getsize(filename)
        except Exception as e:
            raise OSError("Could not get filesize of %s\nError: %s" %
                          (filename, str(e)))

    def writeObjectToFile(self, filelocation, obj):
        """
        Write a object to a file(pickle format)
        @param filelocation: location of the file to which we write
        @param obj: object to pickle and write to a file
        """
        if not filelocation or not obj:
            raise ValueError(
                "You should provide a filelocation or a object as parameters")
        self.logger.silly(
            "Creating pickle and write it to file: %s" % filelocation)
        try:
            pcl = pickle.dumps(obj)
        except Exception as e:
            raise Exception(
                "Could not create pickle from the object \nError: %s" % (str(e)))
        j.sal.fs.writeFile(filelocation, pcl)
        if not self.exists(filelocation):
            raise Exception("File isn't written to the filesystem")

    def readObjectFromFile(self, filelocation):
        """
        Read a object from a file(file contents in pickle format)
        @param filelocation: location of the file
        @return: object
        """
        if not filelocation:
            raise ValueError(
                "You should provide a filelocation as a parameter")
        self.logger.silly("Opening file %s for reading" % filelocation)
        contents = j.sal.fs.fileGetContents(filelocation)
        self.logger.silly("creating object")
        try:
            obj = pickle.loads(contents)
        except Exception as e:
            raise Exception(
                "Could not create the object from the file contents \n Error: %s" % (str(e)))
        return obj

    def md5sum(self, filename):
        """Return the hex digest of a file without loading it all into memory
        @param filename: string (filename to get the hex digest of it) or list of files
        @rtype: md5 of the file
        """
        self.logger.silly(
            'Get the hex digest of file %s without loading it all into memory' % filename)
        if filename is None:
            raise('File name is None in system.fs.md5sum')
        if not isinstance(filename, list):
            filename = [filename]
        digest = hashlib.md5()
        try:
            for filepath in filename:
                with open(filepath, 'rb') as fh:
                    while True:
                        buf = fh.read(4096)
                        if buf == b"":
                            break
                        digest.update(buf)
            return digest.hexdigest()
        except Exception as e:
            raise j.exceptions.RuntimeError(
                "Failed to get the hex digest of the file %sin system.fs.md5sum. Error: %s" % (filename, str(e)))

    def getFolderMD5sum(self, folder):
        files = sorted(self.walk(folder, recurse=1))
        return self.md5sum(files)

    def walkExtended(self, root, recurse=0, dirPattern='*', filePattern='*',
                     followSoftLinks=True, dirs=True, files=True):
        """
        Extended Walk version: seperate dir and file pattern
        @param  root                : start directory to start the search.
        @type   root                : string
        @param  recurse             : search also in subdirectories.
        @type   recurse             : number
        @param  dirPattern          : search pattern to match directory names. Wildcards can be included.
        @type   dirPattern          : string
        @param  filePattern         : search pattern to match file names. Wildcards can be included.
        @type   filePattern         : string
        @param  followSoftLinks     : determine if links must be followed.
        @type   followSoftLinks     : boolean
        @param  dirs                : determine to return dir results.
        @type   dirs                : boolean
        @param  files               : determine to return file results.
        @type   files               : boolean

        @return                     : List of files and / or directories that match the search patterns.
        @rtype                      : list of strings

        General guidelines in the usage of the method be means of some examples come next. For the example in /tmp there is

        * a file test.rtt
        * and ./folder1/subfolder/subsubfolder/small_test/test.rtt

        To find the first test you can use
           j.sal.fs.walkExtended('/tmp/', dirPattern="*tmp*", filePattern="*.rtt")
        To find only the second one you could use
           j.sal.fs.walkExtended('tmp', recurse=0, dirPattern="*small_test*", filePattern="*.rtt", dirs=False)
        """
        self.logger.silly('Scanning directory (walk) %s' % root)
        result = []
        try:
            names = os.listdir(root)
        except os.error:
            return result  # TODO: P2 is this correct?

        dirPattern = dirPattern or '*'
        dirPatList = dirPattern.split(';')
        filePattern = filePattern or '*'
        filePatList = filePattern.split(';')

        for name in names:
            fullname = os.path.normpath(os.path.join(root, name))
            if self.isFile(fullname, followSoftLinks):
                fileOK = False
                dirOK = False
                for fPat in filePatList:
                    if (fnmatch.fnmatch(name, fPat)):
                        fileOK = True
                for dPat in dirPatList:
                    if (fnmatch.fnmatch(os.path.dirname(fullname), dPat)):
                        dirOK = True
                if fileOK and dirOK and files:
                    result.append(fullname)
            if self.isDir(fullname, followSoftLinks):
                for dPat in dirPatList:
                    if (fnmatch.fnmatch(name, dPat) and dirs):
                        result.append(fullname)
            if recurse:
                result = result + self.walkExtended(root=fullname,
                                                    recurse=recurse,
                                                    dirPattern=dirPattern,
                                                    filePattern=filePattern,
                                                    followSoftLinks=followSoftLinks,
                                                    dirs=dirs,
                                                    files=files)

        return result

    def walk(self, root, recurse=0, pattern='*', return_folders=0,
             return_files=1, followSoftlinks=True, str=False, depth=None):
        """This is to provide ScanDir similar function
        It is going to be used wherever some one wants to list all files and subfolders
        under one given directly with specific or none matchers
        """
        # initialize
        result = []
        if depth is not None:
            if depth == 0:
                return result
            depth -= 1
        if str:
            os.path.supports_unicode_filenames = True

        self.logger.silly('Scanning directory (walk)%s' % root)
        # initialize
        result = []

        # must have at least root folder
        try:
            names = os.listdir(root)
        except os.error:
            return result

        # expand pattern
        pattern = pattern or '*'
        pat_list = pattern.split(';')

        # check each file
        for name in names:
            fullname = os.path.normpath(os.path.join(root, name))

            # grab if it matches our pattern and entry type
            for pat in pat_list:
                if (fnmatch.fnmatch(name, pat)):

                    if (self.isFile(fullname, followSoftlinks) and return_files) or (
                            return_folders and self.isDir(fullname, followSoftlinks)):
                        result.append(fullname)
                    continue

            # recursively scan other folders, appending results
            if recurse:
                if self.isDir(fullname) and not self.isLink(fullname):
                    result = result + \
                        self.walk(fullname, recurse, pattern, return_folders,
                                  return_files, followSoftlinks, depth=depth)
        return result

    def getTmpDirPath(self, create=True):
        """
        create a tmp dir name and makes sure the dir exists
        """
        tmpdir = j.sal.fs.joinPaths(j.dirs.TMPDIR, j.data.idgenerator.generateXCharID(10))
        if create is True:
            j.sal.fs.createDir(tmpdir)
        return tmpdir

    def getTmpFilePath(self, cygwin=False):
        """Generate a temp file path
        Located in temp dir of qbase
        @rtype: string representing the path of the temp file generated
        """
        # return tempfile.mktemp())
        tmpdir = j.dirs.TMPDIR
        fd, path = tempfile.mkstemp(dir=tmpdir)
        try:
            real_fd = os.fdopen(fd)
            real_fd.close()
        except (IOError, OSError):
            pass
        if cygwin:
            path = path.replace("\\", "/")
            path = path.replace("//", "/")
        return path

    def getTempFileName(self, dir=None, prefix=''):
        """Generates a temp file for the directory specified
        @param dir: Directory to generate the temp file
        @param prefix: string to start the generated name with
        @rtype: string representing the generated temp file path
        """
        if dir is None:
            return j.sal.fs.joinPaths(j.dirs.TMPDIR, prefix +
                                      str(j.data.idgenerator.generateRandomInt(0, 1000000000000)) + ".tmp")
        else:
            dir = dir or j.dirs.TMPDIR
            return tempfile.mktemp('', prefix, dir)

    def isAsciiFile(self, filename, checksize=4096):
        # TODO: let's talk about checksize feature.
        try:
            with open(filename, encoding='ascii') as f:
                f.read()
                return True
        except UnicodeDecodeError:
            return False

    def isBinaryFile(self, filename, checksize=4096):
        return not self.isAsciiFile(filename, checksize)

    def isAbsolute(self, path):
        return os.path.isabs(path)

    lock = staticmethod(lock)
    lock_ = staticmethod(lock_)
    islocked = staticmethod(islocked)
    unlock = staticmethod(unlock)
    unlock_ = staticmethod(unlock_)

    def validateFilename(self, filename, platform=None):
        '''Validate a filename for a given (or current) platform

        Check whether a given filename is valid on a given platform, or the
        current platform if no platform is specified.

        Rules
        =====
        Generic
        -------
        Zero-length filenames are not allowed

        Unix
        ----
        Filenames can contain any character except 0x00. We also disallow a
        forward slash ('/') in filenames.

        Filenames can be up to 255 characters long.

        Windows
        -------
        Filenames should not contain any character in the 0x00-0x1F range, '<',
        '>', ':', '"', '/', '\', '|', '?' or '*'. Names should not end with a
        dot ('.') or a space (' ').

        Several basenames are not allowed, including CON, PRN, AUX, CLOCK$,
        NUL, COM[1-9] and LPT[1-9].

        Filenames can be up to 255 characters long.

        Information sources
        ===================
        Restrictions are based on information found at these URLs:

         * http://en.wikipedia.org/wiki/Filename
         * http://msdn.microsoft.com/en-us/library/aa365247.aspx
         * http://www.boost.org/doc/libs/1_35_0/libs/filesystem/doc/portability_guide.htm
         * http://blogs.msdn.com/brian_dewey/archive/2004/01/19/60263.aspx

        @param filename: Filename to check
        @type filename: string
        @param platform: Platform to validate against
        @type platform: L{PlatformType}

        @returns: Whether the filename is valid on the given platform
        @rtype: bool
        '''
        platform = platform or j.core.platformtype.myplatform

        if not filename:
            return False

        # When adding more restrictions to check_unix or check_windows, please
        # update the validateFilename documentation accordingly

        def check_unix(filename):
            if len(filename) > 255:
                return False

            if '\0' in filename or '/' in filename:
                return False

            return True

        def check_windows(filename):
            if len(filename) > 255:
                return False

            if os.path.splitext(filename)[0] in ('CON', 'PRN', 'AUX', 'CLOCK$', 'NUL'):
                return False

            if os.path.splitext(filename)[0] in ('COM%d' % i for i in range(1, 9)):
                return False

            if os.path.splitext(filename)[0] in ('LPT%d' % i for i in range(1, 9)):
                return False

            # ASCII characters 0x00 - 0x1F are invalid in a Windows filename
            # We loop from 0x00 to 0x20 (xrange is [a, b[), and check whether
            # the corresponding ASCII character (which we get through the chr(i)
            # function) is in the filename
            for c in range(0x00, 0x20):
                if chr(c) in filename:
                    return False

            for c in ('<', '>', ':', '"', '/', '\\', '|', '?', '*'):
                if c in filename:
                    return False

            if filename.endswith((' ', '.', )):
                return False

            return True

        if platform.isWindows():
            return check_windows(filename)

        if platform.isUnix():
            return check_unix(filename)

        raise NotImplementedError(
            'Filename validation on given platform not supported')

    def find(self, startDir, fileregex):
        """Search for files or folders matching a given pattern
        this is a very weard function, don't use is better to use the list functions
        make sure you do changedir to the starting dir first
        example: find("*.pyc")
        @param fileregex: The regex pattern to match
        @type fileregex: string
        """
        pwd = j.sal.fs.getcwd()
        try:
            self.changeDir(startDir)
            import glob
            return glob.glob(fileregex)
        finally:
            self.changeDir(pwd)

    def grep(self, fileregex, lineregex):
        """Search for lines matching a given regex in all files matching a regex

        @param fileregex: Files to search in
        @type fileregex: string
        @param lineregex: Regex pattern to search for in each file
        @type lineregex: string
        """
        import glob
        import re
        import os
        for filename in glob.glob(fileregex):
            if os.path.isfile(filename):
                f = open(filename, 'r')
                for line in f:
                    if re.match(lineregex, line):
                        print(("%s: %s" % (filename, line)))

    cleanupString = staticmethod(cleanupString)

    def constructDirPathFromArray(self, array):
        """
        Create a path using os specific seperators from a list being passed with directoy.

        @param array str: list of dirs in the path.
        """
        path = ""
        for item in array:
            path = path + os.sep + item
        path = path + os.sep
        if j.core.platformtype.myplatform.isUnix():
            path = path.replace("//", "/")
            path = path.replace("//", "/")
        return path

    def constructFilePathFromArray(self, array):
        """
        Add file name  to dir path.

        @param array str: list including dir path then file name
        """
        path = self.constructDirPathFromArray(array)
        if path[-1] == "/":
            path = path[0:-1]
        return path

    def pathToUnicode(self, path):
        """
        Convert path to unicode. Use the local filesystem encoding. Will return
        path unmodified if path already is unicode.

        Use this to convert paths you received from the os module to unicode.

        @param path: path to convert to unicode
        @type path: basestring
        @return: unicode path
        @rtype: unicode
        """
        from JumpScale.core.main import Dirs
        return Dirs.pathToUnicode(path)

    def targzCompress(self, sourcepath, destinationpath, followlinks=False, destInTar="", pathRegexIncludes=['.[a-zA-Z0-9]*'],
                      pathRegexExcludes=[], contentRegexIncludes=[], contentRegexExcludes=[], depths=[],
                      extrafiles=[]):
        """
        @param sourcepath: Source directory .
        @param destination: Destination filename.
        @param followlinks: do not tar the links, follow the link and add that file or content of directory to the tar
        @param pathRegexIncludes: / Excludes  match paths to array of regex expressions (array(strings))
        @param contentRegexIncludes: / Excludes match content of files to array of regex expressions (array(strings))
        @param depths: array of depth values e.g. only return depth 0 & 1 (would mean first dir depth and then 1 more deep) (array(int))
        @param destInTar when not specified the dirs, files under sourcedirpath will be added to root of
                  tar.gz with this param can put something in front e.g. /qbase3/ prefix to dest in tgz
        @param extrafiles is array of array [[source,destpath],[source,destpath],...]  adds extra files to tar
        (TAR-GZ-Archive *.tar.gz)
        """
        import os.path
        import tarfile

        if not j.sal.fs.isDir(sourcepath):
            raise j.exceptions.RuntimeError(
                "Cannot find file (exists but is not a file or dir) %s" % sourcepath)

        self.logger.silly("Compressing directory %s to %s" %
                          (sourcepath, destinationpath))
        if not j.sal.fs.exists(j.sal.fs.getDirName(destinationpath)):
            j.sal.fs.createDir(j.sal.fs.getDirName(destinationpath))
        t = tarfile.open(name=destinationpath, mode='w:gz')
        if not(followlinks != False or destInTar != "" or pathRegexIncludes != ['.*'] or pathRegexExcludes != []
               or contentRegexIncludes != [] or contentRegexExcludes != [] or depths != []):
            t.add(sourcepath, "/")
        else:
            def addToTar(params, path):
                tarfile = params["t"]
                destInTar = params["destintar"]
                destpath = j.sal.fs.joinPaths(
                    destInTar, j.sal.fs.pathRemoveDirPart(path, sourcepath))
                if j.sal.fs.isLink(path) and followlinks:
                    path = j.sal.fs.readLink(path)
                self.logger.silly("fs.tar: add file %s to tar" % path)
                # print "fstar: add file %s to tar" % path
                if not (j.core.platformtype.myplatform.isWindows() and j.sal.windows.checkFileToIgnore(path)):
                    if self.isFile(path) or self.isLink(path):
                        tarfile.add(path, destpath)
                    else:
                        raise j.exceptions.RuntimeError(
                            "Cannot add file %s to destpath" % destpath)
            params = {}
            params["t"] = t
            params["destintar"] = destInTar
            j.sal.fs.walker.walk(root=sourcepath, callback=addToTar, arg=params,
                                 recursive=True, includeFolders=False,
                                 pathRegexIncludes=pathRegexIncludes, pathRegexExcludes=pathRegexExcludes, contentRegexIncludes=contentRegexIncludes,
                                 contentRegexExcludes=contentRegexExcludes, depths=depths, followlinks=False)

            if extrafiles != []:
                for extrafile in extrafiles:
                    source = extrafile[0]
                    destpath = extrafile[1]
                    t.add(source, j.sal.fs.joinPaths(destInTar, destpath))
        t.close()

    def gzip(self, sourceFile, destFile):
        """
        Gzip source file into destination zip

        @param sourceFile str: path to file to be Gzipped.
        @param destFile str: path to  destination Gzip file.
        """
        import gzip
        f_in = open(sourceFile, 'rb')
        f_out = gzip.open(destFile, 'wb')
        f_out.writelines(f_in)
        f_out.close()
        f_in.close()

    def gunzip(self, sourceFile, destFile):
        """
        Gunzip gzip sourcefile into destination file

        @param sourceFile str: path to gzip file to be unzipped.
        @param destFile str: path to destination folder to unzip folder.
        """
        import gzip
        self.createDir(self.getDirName(destFile))
        f_in = gzip.open(sourceFile, 'rb')
        f_out = open(destFile, 'wb')
        f_out.writelines(f_in)
        f_out.close()
        f_in.close()

    def targzUncompress(self, sourceFile, destinationdir, removeDestinationdir=True):
        """
        compress dirname recursive
        @param sourceFile: file to uncompress
        @param destinationpath: path of to destiniation dir, sourcefile will end up uncompressed in destination dir
        """
        if removeDestinationdir:
            j.sal.fs.removeDirTree(destinationdir)
        if not j.sal.fs.exists(destinationdir):
            j.sal.fs.createDir(destinationdir)
        import tarfile
        if not j.sal.fs.exists(destinationdir):
            j.sal.fs.createDir(destinationdir)

        # The tar of python does not create empty directories.. this causes
        # manny problem while installing so we choose to use the linux tar here
        if j.core.platformtype.myplatform.isWindows():
            tar = tarfile.open(sourceFile)
            tar.extractall(destinationdir)
            tar.close()
            # todo find better alternative for windows
        else:
            cmd = "tar xzf '%s' -C '%s'" % (sourceFile, destinationdir)
            j.sal.process.execute(cmd)
