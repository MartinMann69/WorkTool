"""Validated starter catalog. Entries in SQLite can be maintained by an admin."""
from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
from urllib.parse import urlsplit

DEPARTMENTS = {
    "general": ("General", "Everyday essentials, all in one place.", "G"),
    "it": ("IT", "Your technical workspace, connected.", "IT"),
    "finance": ("Finance", "The tools behind every good decision.", "F"),
    "people": ("People & HR", "A better workday starts with people.", "P"),
    "operations": ("Operations", "Keep your day moving forward.", "O"),
}


@dataclass(frozen=True)
class Entry:
    id: int
    department: str
    kind: str
    title: str
    description: str
    target: str
    arguments: tuple[str, ...] = ()
    restricted: bool = False


def validate_entry(department, kind, title, description, target, arguments):
    if department not in DEPARTMENTS or kind not in {"app", "link"}:
        raise ValueError("Choose a valid workspace and entry type.")
    if not title.strip() or len(title) > 70 or len(description) > 180:
        raise ValueError("Use a title of 1–70 characters and a description of up to 180 characters.")
    if not target.strip() or len(target) > 2048 or any(ord(c) < 32 for c in target):
        raise ValueError("Enter a valid target of up to 2,048 characters.")
    if not isinstance(arguments, (list, tuple)) or any(not isinstance(a, str) or '\x00' in a for a in arguments):
        raise ValueError("Arguments must be a JSON list of strings.")
    if kind == "link":
        try:
            url = urlsplit(target)
            valid = url.scheme in {"http", "https"} and url.hostname and not url.username and not url.password
            _ = url.port
        except ValueError:
            valid = False
        if not valid or any(c.isspace() for c in target) or arguments:
            raise ValueError("Links need an http:// or https:// address without credentials or arguments.")
    elif not target.lower().endswith(".exe") or re.search(r'[<>|"\r\n]', target):
        raise ValueError("Applications must point to a Windows .exe, not a script or shell command.")
    elif target.startswith(("\\\\", "//")):
        raise ValueError("Use a locally installed application, not a network executable.")


def resolve_executable(target: str) -> str | None:
    expanded = os.path.expandvars(target)
    if expanded.startswith(("\\\\", "//")):
        return None
    path = Path(expanded)
    if path.is_absolute():
        return str(path) if path.is_file() else None
    # Only bare executable names may be resolved through PATH.
    if path.name != expanded or '/' in expanded or '\\' in expanded:
        return None
    result = shutil.which(expanded)
    return result if result and not result.startswith(("\\\\", "//")) else None


def starter_entries():
    """100 useful examples: ten applications and ten links per workspace."""
    common_apps = [
        ("Calculator", "Quick calculations, right on your desktop.", "%WINDIR%\\System32\\calc.exe"),
        ("Notepad", "Capture an idea or open a text file.", "%WINDIR%\\System32\\notepad.exe"),
        ("File Explorer", "Find your files and shared folders.", "%WINDIR%\\explorer.exe"),
        ("Snipping Tool", "Capture and share what is on your screen.", "SnippingTool.exe"),
        ("Paint", "Make a quick visual edit or annotation.", "%WINDIR%\\System32\\mspaint.exe"),
        ("Character Map", "Find symbols and special characters.", "%WINDIR%\\System32\\charmap.exe"),
        ("Microsoft Word", "Create documents and polished reports.", "%ProgramFiles%\\Microsoft Office\\root\\Office16\\WINWORD.EXE"),
        ("Microsoft Excel", "Work with spreadsheets and data.", "%ProgramFiles%\\Microsoft Office\\root\\Office16\\EXCEL.EXE"),
        ("Microsoft PowerPoint", "Bring your next presentation together.", "%ProgramFiles%\\Microsoft Office\\root\\Office16\\POWERPNT.EXE"),
        ("Microsoft Outlook", "Open your desktop email and calendar.", "%ProgramFiles%\\Microsoft Office\\root\\Office16\\OUTLOOK.EXE"),
    ]
    apps = {key: list(common_apps) for key in DEPARTMENTS}
    apps["it"][4:7] = [
        ("Visual Studio Code", "Your development environment.", "%LOCALAPPDATA%\\Programs\\Microsoft VS Code\\Code.exe"),
        ("System Information", "Inspect this workstation's configuration.", "%WINDIR%\\System32\\msinfo32.exe"),
        ("Remote Desktop", "Connect to an approved remote workstation.", "%WINDIR%\\System32\\mstsc.exe"),
    ]
    links = {
        "general": [
            ("Microsoft 365", "Your online productivity workspace.", "https://www.microsoft365.com/"),
            ("Teams", "Stay connected with your colleagues.", "https://teams.microsoft.com/"),
            ("Outlook on the web", "Email and calendar in your browser.", "https://outlook.office.com/"),
            ("OneDrive", "Access and share your work files.", "https://onedrive.com/"),
            ("Microsoft To Do", "Make room for what matters today.", "https://to-do.office.com/"),
            ("Microsoft OneNote", "Keep your team's notes together.", "https://www.onenote.com/"),
            ("Microsoft Planner", "Plan tasks and track team progress.", "https://planner.cloud.microsoft/"),
            ("Microsoft Support", "Find help for your everyday tools.", "https://support.microsoft.com/"),
            ("DeepL", "Translate a message or a document.", "https://www.deepl.com/translator"),
            ("Time & Date", "Coordinate across time zones.", "https://www.timeanddate.com/"),
        ],
        "it": [
            ("GitHub", "Repositories and development collaboration.", "https://github.com/"),
            ("Microsoft Learn", "Documentation and technical learning.", "https://learn.microsoft.com/"),
            ("Azure Portal", "Manage your Azure environment.", "https://portal.azure.com/"),
            ("Microsoft Entra", "Your organization's identity workspace.", "https://entra.microsoft.com/"),
            ("Microsoft 365 Admin", "Manage your organization's Microsoft services.", "https://admin.microsoft.com/"),
            ("Atlassian", "Project and service management tools.", "https://www.atlassian.com/"),
            ("Python Documentation", "The Python language reference.", "https://docs.python.org/3/"),
            ("MDN Web Docs", "Reference material for the web.", "https://developer.mozilla.org/"),
            ("Cloudflare", "Network and security services.", "https://dash.cloudflare.com/"),
            ("Docker Hub", "Discover and manage container images.", "https://hub.docker.com/"),
        ],
        "finance": [
            ("SAP", "Enterprise finance and business software.", "https://www.sap.com/"),
            ("Power BI", "Explore your business dashboards.", "https://app.powerbi.com/"),
            ("DATEV", "Accounting and payroll resources.", "https://www.datev.de/"),
            ("ELSTER", "Germany's online tax portal.", "https://www.elster.de/"),
            ("European Central Bank", "Economic data and publications.", "https://www.ecb.europa.eu/"),
            ("Bundesbank", "German central bank resources.", "https://www.bundesbank.de/"),
            ("Eurostat", "European statistics and datasets.", "https://ec.europa.eu/eurostat/"),
            ("Xero", "Online accounting workspace.", "https://www.xero.com/"),
            ("QuickBooks", "Accounting and expense management.", "https://quickbooks.intuit.com/"),
            ("Excel for the web", "Open your online spreadsheet workspace.", "https://excel.cloud.microsoft/"),
        ],
        "people": [
            ("Personio", "People operations and HR software.", "https://www.personio.com/"),
            ("Workday", "People and workforce management.", "https://www.workday.com/"),
            ("BambooHR", "Your people management platform.", "https://www.bamboohr.com/"),
            ("LinkedIn", "Connect with candidates and colleagues.", "https://www.linkedin.com/"),
            ("Indeed", "Recruitment and job discovery.", "https://www.indeed.com/"),
            ("Microsoft Forms", "Create surveys and collect feedback.", "https://forms.office.com/"),
            ("Microsoft Bookings", "Coordinate interviews and appointments.", "https://outlook.office.com/bookings/"),
            ("Coursera", "Learning and professional development.", "https://www.coursera.org/"),
            ("LinkedIn Learning", "Build skills across your organization.", "https://www.linkedin.com/learning/"),
            ("Bundesagentur für Arbeit", "Employment information and resources.", "https://www.arbeitsagentur.de/"),
        ],
        "operations": [
            ("Trello", "Organize work with visual boards.", "https://trello.com/"),
            ("Asana", "Coordinate work and project delivery.", "https://app.asana.com/"),
            ("Monday.com", "Manage your team's workflows.", "https://monday.com/"),
            ("Notion", "Bring project knowledge together.", "https://www.notion.so/"),
            ("Miro", "Collaborate on a shared canvas.", "https://miro.com/"),
            ("DHL Tracking", "Check your shipment's progress.", "https://www.dhl.com/"),
            ("UPS Tracking", "Find shipment and delivery information.", "https://www.ups.com/"),
            ("FedEx", "Shipping and logistics resources.", "https://www.fedex.com/"),
            ("Google Maps", "Plan a visit or find a location.", "https://maps.google.com/"),
            ("Power Automate", "Streamline recurring business tasks.", "https://make.powerautomate.com/"),
        ],
    }
    for dept in DEPARTMENTS:
        for kind, collection in (("app", apps[dept]), ("link", links[dept])):
            for title, description, target in collection:
                yield dept, kind, title, description, target, []
