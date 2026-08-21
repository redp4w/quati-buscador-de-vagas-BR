from .adzuna import AdzunaPlugin
from .ats import (
    AshbyAPIPlugin,
    GreenhouseAPIPlugin,
    LeverAPIPlugin,
    RecruiteeAPIPlugin,
    SmartRecruitersAPIPlugin,
    WorkablePublicPlugin,
)
from .inhire import InHirePlugin
from .registry import build_plugins
from .structured import (
    AshbyPlugin,
    EmpregandoBrasilPlugin,
    EmpregosPlugin,
    GreenhousePlugin,
    GupyPlugin,
    IndeedPlugin,
    LatoJobsPlugin,
    LeverPlugin,
    LinkedInPlugin,
    MindsightPlugin,
    SolidesPlugin,
    VagasComPlugin,
    WorkdayPlugin,
)

__all__ = [
    "AdzunaPlugin",
    "AshbyAPIPlugin",
    "AshbyPlugin",
    "build_plugins",
    "EmpregandoBrasilPlugin",
    "EmpregosPlugin",
    "GupyPlugin",
    "GreenhousePlugin",
    "GreenhouseAPIPlugin",
    "IndeedPlugin",
    "InHirePlugin",
    "LatoJobsPlugin",
    "LeverPlugin",
    "LeverAPIPlugin",
    "LinkedInPlugin",
    "MindsightPlugin",
    "RecruiteeAPIPlugin",
    "SolidesPlugin",
    "SmartRecruitersAPIPlugin",
    "VagasComPlugin",
    "WorkablePublicPlugin",
    "WorkdayPlugin",
]
