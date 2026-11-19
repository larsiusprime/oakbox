/* OAK box.exe: what the Start menu and the desktop start (and the portable bundle's double-click). It runs the
 * bundled Python beside it, without a console:
 *
 *     <its folder>\python\pythonw.exe -X utf8 -m oakbox [its own arguments]
 *
 * and waits for it, so OAK box is "OAK box" in Task Manager, with its own icon and version. Python runs in a job
 * object that ends it when this does: ending OAK box.exe (Task Manager, a crash) ends the app, which leaves nothing
 * holding the files an update or the uninstaller replaces. Only Python itself is in the job (silent breakaway):
 * what it starts (a browser, Explorer, its runs) is its own business (runs follow the app: oakbox/steps.py).
 * If Python can't be started, it says so in a message box: a click is never met with nothing.
 *
 * Built on Linux with MinGW (packaging/build_bundle.sh). */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <wchar.h>

#define TITLE L"OAK box"

static int fail(const wchar_t *what, const wchar_t *path) {
    wchar_t text[2048];
    DWORD err = GetLastError();
    wchar_t sys[512] = L"";
    FormatMessageW(FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS, NULL, err, 0, sys, 512, NULL);
    _snwprintf(text, 2048, L"OAK box couldn't start: %ls\n\n%ls\n\n%ls\nReinstalling OAK box should fix it.", what,
               path, sys);
    text[2047] = 0;
    MessageBoxW(NULL, text, TITLE, MB_ICONERROR | MB_OK);
    return 1;
}

/* The command line after the program's own name (which may be quoted, and may hold spaces). */
static const wchar_t *after_program(const wchar_t *cmd) {
    if (*cmd == L'"') {
        cmd++;
        while (*cmd && *cmd != L'"') cmd++;
        if (*cmd) cmd++;
    } else {
        while (*cmd && *cmd != L' ' && *cmd != L'\t') cmd++;
    }
    while (*cmd == L' ' || *cmd == L'\t') cmd++;
    return cmd;
}

int WINAPI wWinMain(HINSTANCE inst, HINSTANCE prev, PWSTR args, int show) {
    (void)inst, (void)prev, (void)args, (void)show;
    static wchar_t self[32768], dir[32768], python[32768], cmd[40000];
    DWORD n = GetModuleFileNameW(NULL, self, 32768);
    if (n == 0 || n >= 32768) return fail(L"its own folder can't be found.", L"");
    wcscpy(dir, self);
    wchar_t *slash = wcsrchr(dir, L'\\');
    if (!slash) return fail(L"its own folder can't be found.", self);
    *slash = 0;
    _snwprintf(python, 32768, L"%ls\\python\\pythonw.exe", dir);
    python[32767] = 0;
    if (GetFileAttributesW(python) == INVALID_FILE_ATTRIBUTES) return fail(L"its Python is missing.", python);
    _snwprintf(cmd, 40000, L"\"%ls\" -X utf8 -m oakbox %ls", python, after_program(GetCommandLineW()));
    cmd[39999] = 0;

    HANDLE job = CreateJobObjectW(NULL, NULL);
    if (job) {
        JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits;
        ZeroMemory(&limits, sizeof limits);
        limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK;
        SetInformationJobObject(job, JobObjectExtendedLimitInformation, &limits, sizeof limits);
    }
    STARTUPINFOW si;
    PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof si);
    si.cb = sizeof si;
    ZeroMemory(&pi, sizeof pi);
    if (!CreateProcessW(python, cmd, NULL, NULL, FALSE, CREATE_SUSPENDED, NULL, dir, &si, &pi))
        return fail(L"its Python wouldn't start.", python);
    if (job) AssignProcessToJobObject(job, pi.hProcess); /* if it can't be (an older Windows), it still runs */
    ResumeThread(pi.hThread);
    CloseHandle(pi.hThread);
    WaitForSingleObject(pi.hProcess, INFINITE);
    DWORD code = 0;
    GetExitCodeProcess(pi.hProcess, &code);
    CloseHandle(pi.hProcess);
    return (int)code;
}
