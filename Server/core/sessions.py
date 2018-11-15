import functools
import core.state as state
from core.session import Session
from core.job import Job
from time import gmtime, strftime
from prompt_toolkit.formatted_text import HTML
from core.utils import command, register_cli_commands, print_info, print_good
from core.completers import STCompleter
from core.events import NEW_SESSION, SESSION_STAGED, SESSION_CHECKIN, NEW_JOB, JOB_RESULT
from core.ipcserver import ipc_server
from terminaltables import AsciiTable


@register_cli_commands
class Sessions:
    def __init__(self, prompt_session):
        self.name = 'sessions'
        self.prompt = HTML('ST (<ansired>sessions</ansired>) ≫ ')
        self.completer = STCompleter(self)
        self.prompt_session = prompt_session

        self.selected = None
        self.sessions = []

        ipc_server.attach(SESSION_STAGED, self.__notify_session_staged)
        ipc_server.attach(SESSION_CHECKIN, self.__session_checked_in)
        ipc_server.attach(NEW_JOB, self.__add_job)
        ipc_server.attach(JOB_RESULT, self.__job_result)

    def __notify_session_staged(self, msg):
        print_info(msg)

    def __session_checked_in(self, checkin_tuple):
        guid, remote_addr, data = checkin_tuple
        for session in self.sessions:
            if session.guid == guid:
                session.checked_in()
                return session.get_job(data)

        session = Session(guid, remote_addr)
        print_good(f"New session {session.guid} connected! ({session.address})")
        self.sessions.append(session)
        state.SESSIONS = len(self.sessions)
        return session.get_job(data)

    def __add_job(self, job_tuple):
        guid, job = job_tuple
        if guid.lower() == 'all':
            for session in self.sessions:
                session.add_job(job)
        else:
            for session in self.sessions:
                if session.guid == guid:
                    session.add_job(job)

    def __job_result(self, result):
        guid, job_id, data = result
        for session in self.sessions:
            if session.guid == guid:
                job = session.get_job_by_id(job_id)
                results = job.get_results(data)

                print_good(f"{guid} returned job result (id: {job_id})")
                print(results['result'])

    @command
    def list(self, guid: str):
        """
        Get available sessions

        Usage: list [<guid>] [-h]

        Arguments:
            guid  filter by session's guid
        """

        table_data = [
            ["GUID", "User", "Address", "Last Checkin"]
        ]

        for session in self.sessions:
            try:
                username = f"*{session.data['username']}@{session.data['domain']}" if session.data['high_integrity'] else f"{session.data['username']}@{session.data['domain']}"
            except KeyError:
                username = ''

            table_data.append([
                session.guid,
                username,
                session.address,
                strftime("h %H m %M s %S", gmtime(session.last_check_in()))
            ])

        table = AsciiTable(table_data)
        print(table.table)

    @command
    def info(self, guid: str):
        """
        Get session info

        Usage: info <guid> [-h]

        Arguments:
            guid  filter by session's guid
        """

        for session in self.sessions:
            if session.guid == guid:
                table_data = [["Name", "Value"]]
                for k, v in session.data.items():
                    table_data.append([k.capitalize(), v])
                table = AsciiTable(table_data)
                print(table.table)
