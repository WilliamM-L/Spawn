#!/usr/bin/python2.7
import random
import subprocess
import os
import sys

import pexpect

password_re = "(?i)password:\s*$"
prompt_re = "[\$\#] $"
yes_no_re = "\(yes/no\)\?\s*$"

EOF = pexpect.EOF
TIMEOUT = pexpect.TIMEOUT


class FailedProcess(Exception):
    """Raised when a process run from subprocess terminates abnormally.

    :param message: Message to be stored when the exception is raised.
    :type message: str

    :param exitCode: Exit code of the failed process.
    :type exitCode: int
    """

    def __init__(self, message="Command Failed!", exitCode=1):
        # type: (str, int) -> FailedProcess
        Exception.__init__(self, message)
        self.message = message
        self.exitCode = exitCode


class FailedChild(FailedProcess):
    """Raised if a spawned process terminates abnormally.

    :param spawned: Spawned child that failed
    :type spawned: NelsSpawn

    :param message: Message to be stored when the exception is raised.
    :type message: str

    :param passwordSent: Password that was sent during the authentication phase.
    :type passwordSent: str

    :param exitCode: Exit code of the failed process.
    :type exitCode: int
    """

    def __init__(self, spawned, message, passwordSent=None, exitCode=1):
        # type: (NelsSpawn, str, str, int) -> FailedChild
        super(FailedChild, self).__init__(message, exitCode)
        command = ""
        for item in spawned.child.args:
            command += item + " "
        self.command = command
        self.passwordSent = passwordSent
        self.buffer = spawned.child.before + str(spawned.child.after)
        self.message = message + "\nCommand: " + command + "\nPassword: " + str(passwordSent) + "\nExit code: " + str(self.exitCode)
        spawned.child.close()
        self.child = spawned.child
        if type(NelsSpawnLowInteractivity):
            if os.path.isfile(spawned.logFilePath):
                with open(spawned.logFilePath, 'r') as log:
                    self.log = log.read()


def getParentDirectory(path, iterations=1):
    """Returns the n-th parent directory of the give path"""
    for i in range(iterations):
        path = os.path.realpath(os.path.join(path, os.pardir))
    return path


def cd(path):
    os.chdir(path)


def run(command, cwd=None):
    print command
    # subprocess.call automatically prints the output to stdout, returns the exit code
    # call() also waits for the process to be done
    procExitCode = subprocess.call(command, cwd=cwd, shell=True)
    if procExitCode != 0:
        raise FailedProcess(message="Command Failed: " + command, exitCode=procExitCode)


class NelsSpawn:
    """ **Base class, not intented to be used on its own.**

    Contains the base functions which are used by the subclasses.

    :param dictionary: Dictionary which contains the placeholders and what they should be replaced by.
    :type dictionary: dict

    :param user: User to be contacted at the host.
    :type user: str

    :param node: Address of the node that will be contacted.
    :type node: str
    """

    stdTimeout = 600

    def __init__(self, dictionary, user, node):
        # type: (dict, str, str) -> NelsSpawn
        parameters = dictionary
        parameters.update({"user": user})
        parameters.update({"node": node})
        self.parameters = parameters
        self.parameters = dictionary
        self.child = None

    def __str__(self):
        return "parameters: {0},\n child: {1} \n".format(self.parameters, self.child)

    def updateParameters(self, toUpdate):
        """Updates the parameter dictionary.

        :param toUpdate: Dictionary that will be used to update the parameter dictionary.
        :type toUpdate: dict
        """
        if type(toUpdate) is dict:
            self.parameters.update(toUpdate)
        else:
            print "ONLY dictionaries are used to update the parameters dictionary."

    def format(self, string):
        """Formats the given string by replacing all the {placeholders} by their associated value in self.parameters"""
        if string is not None:
            return string.format(**self.parameters)

    def createChild(self, command, cwd=None):
        """Creates a spawned child with a formatted command and returns it.

        :param command: Command to be formatted and executed that is given to the created child.
        :type command: str

        :param cwd: Working directory from which the child will execute the command.
        :type cwd: str

        :returns: A object executing the given command at the given location, printing all logs to stdout.
        :rtype: pexpect.spawn
        """
        if self.child is not None:
            self.child.close()
        command = self.format(command)
        print command
        return pexpect.spawn(command, cwd=cwd, logfile=sys.stdout)

    def close(self):
        """Closes a child."""
        if self.child is not None:
            self.child.close()

    def run(self, command, cwd=None):
        """Runs a formatted commands locally in a certain location, in bash.

        :param command: Command to be formatted and then executed locally.
        :type command: str

        :param cwd: Working directory from which command will run.
        :type cwd: str
        """
        command = self.format(command)
        print command
        # subprocess.call automatically prints the output to stdout, returns the exit code
        # call() also waits for the process to be done
        procExitCode = subprocess.call(command, cwd=self.format(cwd), shell=True)
        if procExitCode != 0:
            raise FailedProcess(message="Command Failed: "+command, exitCode=procExitCode)

    def cd(self, path):
        os.chdir(self.format(path))

    def ssh_keygen(self, modifier="-R"):
        self.run('ssh-keygen '+modifier+' "{node}"')



class NelsSpawnHighInteractivity(NelsSpawn):
    """**High interactivity variant of NelsSpawn**

    This class is meant to be used when NelsSpawnLowInteractivity is not flexible enough.
    Instead of sending only one command with the authentication information and then log off,
    this class will keep the session open(ssh for example), allowing for more commands to be sent and patterns to be expected.
    """
    pass

    def spawn_ssh(self, modifier="-o LogLevel=Error", user="{user}", node="{node}"):
        """Spawns an open ssh session.

            *The standard is to log only the errors and contact the user and node provided by the NelsSpawn object.*

        :param modifier: Extra parameter given to ssh command.
        :type modifier: str

        :param user: User to be contacted.
        :type user: str

        :param node: Address of the node to be contacted.
        :type node: str
        """
        self.child = self.createChild("/usr/bin/ssh " + modifier + " " + user + "@" + node)

    def spawn_sh(self, command, cwd=None):
        """Spawns an instance of an executable. [not sure about the terminology]

            *This can't run complex commands with special characters such as &&, |, *, it only runs executables*

        :param command: Program to run with parameters.
        :type command: str

        :param cwd: Location where the command will be executed.
        :type cwd: str
        """
        self.child = self.createChild(command, cwd=cwd)

    def spawn_ssh_copy_id(self, user="{user}", node="{node}"):
        """Spawns an open ssh-copy-id session.

            *The standard is to contact the user and node provided by the NelsSpawn object.*

        :param user: User to be contacted.
        :type user: str

        :param node: Address of the node to be contacted.
        :type node: str
        """
        self.child = self.createChild("ssh-copy-id " + user + "@" + node)

    def send(self, command):
        """Sends a formatted command to an **already spawned** child.

        :param command: Command to be formatted and run on the spawned child.
        :type command: str

        This is mainly used for ssh sessions that run more than one command.
        """
        self.child.sendline(self.format(command))

    def expect(self, patterns, timeout=NelsSpawn.stdTimeout):
        # if a list is given, it will return the index at which it was found.
        """Sends a formatted command to an **already spawned** child.

        This is mainly used for ssh sessions that run more than one command.

        :param patterns: List of patterns to look for.
        :type patterns: list

        :param timeout: Number of seconds for which this function will look for matches.
        :type timeout: int

        :returns: The index that points to the pattern that was matched.
        :rtype: int
        """
        return self.child.expect(patterns, timeout=timeout)

    def fail(self, message, exitCode, passwordSent=None):
        """Raises a FailedChild exception.

        :param message: Message to be passed to the exception.
        :type message: str

        :param exitCode: Exit code to be emitted.
        :type exitCode: int

        :param passwordSent: If a password was sent, it should be specified here.
        :type passwordSent: str
        """
        raise FailedChild(self, message, passwordSent=passwordSent, exitCode=exitCode)


class NelsSpawnLowInteractivity(NelsSpawn):
    """**Low interactivity variant of NelsSpawn**

    This class is meant to be used to send commands of the form: ssh user@host "command".
    Each child spawned with the class sends one command (may be complex), sends login info,
    and then looks for patterns and exits immediately.

    In this class the password is a mandatory parameter. Temporary passwords may be used however.
    Should the password be changed permanently, use updatePassword().
    """

    def __init__(self, dictionary, password, user, node, passwordMandatory=True):
        # type: (dict, str, str, str, bool) -> NelsSpawnLowInteractivity
        NelsSpawn.__init__(self, dictionary, user, node)
        self.password = password
        self.passwordMandatory = passwordMandatory
        # The path of the log is randomised
        self.logFilePath = "/tmp/VNFPythonScripts{}.log".format(random.randint(0, 999999999999999))
        # creating the file without writing to it in case the child is closed without doing anything
        os.mknod(self.logFilePath)

    def __str__(self):
        return " password: {0},\n parameters: {1},\n child: {2} \n".format(self.password, self.parameters, self.child)

    def createChild(self, command, cwd=None):
        """Creates a spawned child with a formatted command and returns it.

        *The logs aren't printed by default and they don't need to be since AuthenticateAndExit handles that
        and is executed automatically when a new spawn is created. The logfile will be printed if the child fails.*

        :param command: Command to be formatted and executed that is given to the created child.
        :type command: str

        :param cwd: Working directory from which the child will execute the command.
        :type cwd: str

        :returns: A object executing the given command at the given location, printing all logs to a logfile.
        :rtype: pexpect.spawn
        """
        command = self.format(command)
        print command
        return pexpect.spawn(command, cwd=cwd, logfile=open(self.logFilePath, 'w'))

    def close(self, printLog=False):
        """Closes a child, may print its logs, and deletes the logs.

        :param printLog: Whether the logs of the closed child should be printed.
        :type printLog: bool
        """
        if self.child is not None:
            self.child.close()
            if printLog:
                if os.path.isfile(self.logFilePath):
                    with open(self.logFilePath, 'r') as log:
                        print log.read()
        os.remove(self.logFilePath)

    def authenticateAndExit(self, tmpPassword=None, failureMessage="Command Failed!", extraPatternsAndExitCodes=None,
                            extraPatternsAndCommands=None):
        """Sends the login information as the command is executed and
         raises the appropriate exceptions in case of failure.

        :param tmpPassword: Temporary password that will be used when contacting the node.
        :type tmpPassword: str

        :param failureMessage: Failure message to send if the child fails.
        :type failureMessage: str

        :param extraPatternsAndExitCodes: Extra patterns to look for and their associated error codes to emit when matched.
        :type extraPatternsAndExitCodes: dict

        :param extraPatternsAndCommands: Extra patterns to look for and their associated commands to send to the target when matched.
        :type extraPatternsAndCommands: dict
        """
        if extraPatternsAndExitCodes is None:
            extraPatternsAndExitCodes = {}
        if extraPatternsAndCommands is None:
            extraPatternsAndCommands = {}

        extraPatternsAndExitCodes.update({pexpect.EOF: 2, pexpect.TIMEOUT: 3})

        # in case it is never set
        exitCode = False
        if tmpPassword is not None:
            passwordSent = tmpPassword
        else:
            passwordSent = self.password

        originalPatterns = [password_re, yes_no_re] + extraPatternsAndCommands.keys()
        patterns = originalPatterns + extraPatternsAndExitCodes.keys()
        responses = [passwordSent, "yes"] + extraPatternsAndExitCodes.values() + extraPatternsAndCommands.values()

        while True:
            index = self.child.expect(patterns, timeout=NelsSpawn.stdTimeout)
            if index == 0:
                self.child.sendline(passwordSent)
                break
            elif index < len(originalPatterns):
                self.child.sendline(responses[index])
            else:
                exitCode = responses[index]
                # exit codes 2 and 3 are reserved for EOF and TIMEOUT respectively
                if exitCode == 2:
                    if self.passwordMandatory:
                        failureMessage = "EOF encountered before sending the password!"
                    else:
                        # A password may not be needed, the process is done
                        break
                elif exitCode == 3:
                    failureMessage = "Child timed out before the password could be sent!"
                break
        if exitCode and self.passwordMandatory:
            print self.child.read()
            self.child.close()
            raise FailedChild(self, failureMessage, passwordSent=passwordSent, exitCode=exitCode)

        wrongPassword = False
        processNotDone = False

        index = self.child.expect([password_re, pexpect.TIMEOUT, pexpect.EOF], timeout=NelsSpawn.stdTimeout)
        # if EOF is caught, we know the process is now done
        # the child.before buffer should be printed before it it closed, will have access to many more bytes
        if index == 0:
            # requesting the password again, the wrong one was sent.
            wrongPassword = True
        elif index == 1:
            print self.child.before
            processNotDone = True
        elif index == 2:
            print self.child.before

        # closing the spawned process to access the exitstatus and signalstatus
        # signalstatus is None if the child terminated successfully
        # in case of abnormal termination, the signal will be stored in signalstatus and exitstatus will be None
        self.child.close()

        if self.child.signalstatus is not None or self.child.exitstatus != 0:
            print "child status: " + str(self.child.status)
            print "child exit status: " + str(self.child.exitstatus)
            if wrongPassword:
                failureMessage = "Invalid Password!"
            elif processNotDone:
                failureMessage = "The process timed out!"
            raise FailedChild(self, failureMessage, passwordSent=passwordSent, exitCode=self.child.exitstatus)

    def spawn_ssh(self, command, modifier="-o LogLevel=Error", user="{user}", node="{node}", tmpPassword=None,
                  failureMessage="Command Failed!", extraPatternsAndExitCodes=None, extraPatternsAndCommands=None):
        """Spawns a closed ssh session.

        A closed ssh session is one that sends a single command, authenticates and then exits.

            *The standard is to log only the errors and contact the user and node provided by the NelsSpawn object.*

        :param command: Command to be formatted and run on the target machine.
        :type command: str

        :param modifier: Extra parameter given to ssh command.
        :type modifier: str

        :param user: User to be contacted.
        :type user: str

        :param node: Address of the node to be contacted.
        :type node: str

        :param tmpPassword: Temporary password that will be used when contacting the node.
        :type tmpPassword: str

        :param failureMessage: Failure message to send if the child fails.
        :type failureMessage: str

        :param extraPatternsAndExitCodes: Extra patterns to look for and their associated error codes to emit when matched.
        :type extraPatternsAndExitCodes: dict

        :param extraPatternsAndCommands: Extra patterns to look for and their associated commands to send to the target when matched.
        :type extraPatternsAndCommands: dict
        """
        self.child = self.createChild("/usr/bin/ssh "+modifier+" "+user+"@" + node + " '" + command + "'")
        self.authenticateAndExit(tmpPassword=tmpPassword, failureMessage=failureMessage,
                                 extraPatternsAndExitCodes=extraPatternsAndExitCodes,
                                 extraPatternsAndCommands=extraPatternsAndCommands)

    def spawn_scp(self, command, modifier="-o LogLevel=Error", tmpPassword=None,
                  failureMessage="Command Failed!", cwd=None, extraPatternsAndExitCodes=None,
                  extraPatternsAndCommands=None):
        """Spawns a scp process.

            *The standard is to log only the errors and contact the user and node provided by the NelsSpawn object.*
            *passing that command through bash so that meta characters (*, |) are interpreted*

        :param command: Command to be formatted and run.
        :type command: str

        :param modifier: Extra parameter given to scp command.
        :type modifier: str

        :param tmpPassword: Temporary password that will be used when contacting the node.
        :type tmpPassword: str

        :param failureMessage: Failure message to send if the child fails.
        :type failureMessage: str

        :param cwd: Working directory from which the child will execute the command.
        :type cwd: str

        :param extraPatternsAndExitCodes: Extra patterns to look for and their associated error codes to emit when matched.
        :type extraPatternsAndExitCodes: dict

        :param extraPatternsAndCommands: Extra patterns to look for and their associated commands to send to the target when matched.
        :type extraPatternsAndCommands: dict
        """
        self.child = self.createChild("/bin/bash -c '/usr/bin/scp " + modifier + " " + command + "'", cwd=cwd)
        self.authenticateAndExit(tmpPassword=tmpPassword, failureMessage=failureMessage,
                                 extraPatternsAndExitCodes=extraPatternsAndExitCodes,
                                 extraPatternsAndCommands=extraPatternsAndCommands)
