from __future__ import annotations

from quati.config import JobSourceConfiguration

from .adzuna import AdzunaPlugin
from .ats import (
    AshbyAPIPlugin,
    GreenhouseAPIPlugin,
    LeverAPIPlugin,
    RecruiteeAPIPlugin,
    SmartRecruitersAPIPlugin,
    WorkablePublicPlugin,
)
from .base import JobPlugin
from .inhire import InHirePlugin
from .structured import (
    EmpregandoBrasilPlugin,
    EmpregosPlugin,
    GupyPlugin,
    IndeedPlugin,
    LatoJobsPlugin,
    LinkedInPlugin,
    MindsightPlugin,
    SolidesPlugin,
    VagasComPlugin,
    WorkdayPlugin,
)


def build_plugins(
    source_configuration: JobSourceConfiguration | None = None,
) -> dict[str, JobPlugin]:
    configuration = source_configuration or JobSourceConfiguration()
    plugins: list[JobPlugin] = [
        AdzunaPlugin(configuration.adzuna_app_id, configuration.adzuna_app_key),
        InHirePlugin(),
        GreenhouseAPIPlugin(),
        LeverAPIPlugin(),
        WorkdayPlugin(),
        AshbyAPIPlugin(),
        SmartRecruitersAPIPlugin(),
        RecruiteeAPIPlugin(),
        WorkablePublicPlugin(),
        EmpregosPlugin(),
        EmpregandoBrasilPlugin(),
        SolidesPlugin(),
        MindsightPlugin(),
        LatoJobsPlugin(),
        GupyPlugin(),
        LinkedInPlugin(),
        IndeedPlugin(),
        VagasComPlugin(),
    ]
    return {plugin.name: plugin for plugin in plugins}
