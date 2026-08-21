from __future__ import annotations

import argparse
import os
from pathlib import Path

from loguru import logger

from quati.core.browser import PlaywrightBrowser
from quati.core.browser.url_safety import validate_public_https_url
from quati.plugins import build_plugins
from quati.services import JobCollector, SearchScheduler
from quati.storage import SQLiteJobRepository


def _database_path() -> Path:
    return Path(os.environ.get("QUATI_DB", "data/quati.sqlite3"))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Q.U.A.T.I. local")
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect = subparsers.add_parser("collect", help="Coleta uma fonte pública")
    collect.add_argument("source", help="Fonte, como inhire ou greenhouse")
    collect.add_argument("url", help="URL pública da busca ou empresa")

    subparsers.add_parser("run-due", help="Executa agendamentos vencidos")
    subparsers.add_parser("status", help="Mostra estatísticas locais")
    schedule = subparsers.add_parser("schedule", help="Cria um agendamento local")
    schedule.add_argument("source", help="Fonte, como inhire ou greenhouse")
    schedule.add_argument("url", help="URL pública da busca ou empresa")
    schedule.add_argument("--interval", type=int, default=1_440, help="Intervalo em minutos")
    subparsers.add_parser("alerts", help="Lista alertas locais não lidos")
    subparsers.add_parser("applications", help="Lista o acompanhamento de candidaturas")
    return parser


def main() -> int:
    logger.remove()
    logger.add(lambda message: print(message, end=""), backtrace=False, diagnose=False)
    args = _parser().parse_args()
    repository = SQLiteJobRepository(_database_path())
    plugins = build_plugins()
    try:
        if args.command == "status":
            logger.info("{}", repository.stats())
            return 0
        if args.command == "collect":
            plugin = plugins.get(args.source)
            if plugin is None:
                raise ValueError("Fonte não suportada.")
            result = JobCollector(repository, PlaywrightBrowser()).collect(plugin, args.url)
            logger.info(
                "Coleta concluída: {} encontradas, {} novas, {} atualizadas.\n",
                result.found,
                result.inserted,
                result.updated,
            )
            return 0
        if args.command == "schedule":
            plugin = plugins.get(args.source)
            if plugin is None:
                raise ValueError("Fonte não suportada.")
            url = validate_public_https_url(args.url, plugin.allowed_hosts)
            schedule = repository.create_schedule(plugin.name, url, interval_minutes=args.interval)
            logger.info("Agendamento #{} criado.\n", schedule.id)
            return 0
        if args.command == "alerts":
            for alert in repository.list_alerts(unread_only=True):
                logger.info("{} | {}\n", alert.kind, alert.message)
            return 0
        if args.command == "applications":
            for application in repository.list_applications():
                job = repository.get_job(application.job_id)
                logger.info(
                    "{} | {} | {} | {}\n",
                    application.status,
                    job.title,
                    job.company,
                    job.url,
                )
            return 0
        results = SearchScheduler(repository, PlaywrightBrowser()).run_due(plugins)
        logger.info("{} agendamento(s) executado(s).\n", len(results))
        return 0
    except (RuntimeError, ValueError) as exc:
        logger.error("{}\n", str(exc)[:500])
        return 1
    finally:
        repository.close()


if __name__ == "__main__":
    raise SystemExit(main())
