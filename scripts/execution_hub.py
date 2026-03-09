#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import NoReturn


DEFAULT_HUB = Path("/mascarade/docs/EXECUTION_HUB.md")
DEFAULT_MACHINE_PROFILES = Path("/mascarade/docs/MACHINE_PROFILES.json")
VALID_STATUSES = {"PENDING", "IN_PROGRESS", "BLOCKED", "DONE", "DEFERRED"}
GLOBAL_SCOPES = {"-", "", "all", "any", "global"}


@dataclass
class Lot:
    lot_id: str
    repo: str
    title: str
    status: str
    scope: str
    depend: str
    validation: str

    def dependencies(self) -> list[str]:
        raw = self.depend.strip()
        if not raw or raw == "-":
            return []
        return [item.strip() for item in raw.split(",") if item.strip()]

    def scope_tokens(self) -> list[str]:
        raw = self.scope.strip()
        if not raw or raw == "-":
            return ["global"]
        return [item.strip() for item in raw.split(",") if item.strip()]

    def as_dict(self) -> dict[str, str]:
        return {
            "id": self.lot_id,
            "repo": self.repo,
            "title": self.title,
            "status": self.status,
            "scope": self.scope,
            "depend": self.depend,
            "validation": self.validation,
        }


@dataclass
class MachineProfile:
    name: str
    aliases: set[str]
    capabilities: set[str]

    def display_capabilities(self) -> str:
        if not self.capabilities:
            return "-"
        return ", ".join(sorted(self.capabilities))


def _fail(message: str, code: int = 1) -> NoReturn:
    print(message, file=sys.stderr)
    raise SystemExit(code)


def _clean_cell(value: str) -> str:
    cleaned = value.strip()
    if cleaned.startswith("`") and cleaned.endswith("`") and cleaned.count("`") == 2:
        cleaned = cleaned[1:-1]
    return cleaned.strip()


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _replace_section(text: str, heading: str, body: str) -> str:
    pattern = re.compile(
        rf"(^## {re.escape(heading)}\n)(.*?)(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    if not pattern.search(text):
        _fail(f"section introuvable: {heading}")
    return pattern.sub(lambda match: f"{match.group(1)}{body.rstrip()}\n\n", text, count=1)


def _table_bounds(text: str) -> tuple[int, int]:
    match = re.search(
        r"^## File d'execution\n(?P<body>.*?)(?=^## Lot en cours)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if not match:
        _fail("section 'File d'execution' introuvable")
    return match.start("body"), match.end("body")


def parse_lots(text: str) -> list[Lot]:
    start, end = _table_bounds(text)
    body = text[start:end]
    lots: list[Lot] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line.startswith("|"):
            continue
        if line.startswith("| ID ") or line.startswith("| --- "):
            continue
        cells = [cell for cell in raw_line.strip().split("|")[1:-1]]
        if len(cells) == 7:
            lot = Lot(
                lot_id=_clean_cell(cells[0]),
                repo=_clean_cell(cells[1]),
                title=_clean_cell(cells[2]),
                status=_clean_cell(cells[3]),
                scope=_clean_cell(cells[4]) or "global",
                depend=_clean_cell(cells[5]),
                validation=_clean_cell(cells[6]),
            )
        elif len(cells) == 6:
            lot = Lot(
                lot_id=_clean_cell(cells[0]),
                repo=_clean_cell(cells[1]),
                title=_clean_cell(cells[2]),
                status=_clean_cell(cells[3]),
                scope="global",
                depend=_clean_cell(cells[4]),
                validation=_clean_cell(cells[5]),
            )
        else:
            continue
        lots.append(lot)
    return lots


def format_lot(lot: Lot) -> str:
    return (
        f"| `{lot.lot_id}` | `{lot.repo}` | {lot.title} | `{lot.status}` | "
        f"`{lot.scope or 'global'}` | `{lot.depend or '-'}` | {lot.validation} |"
    )


def write_lots(text: str, lots: list[Lot]) -> str:
    start, end = _table_bounds(text)
    new_body = (
        "\n| ID | Repo canonique | Titre | Statut | Portee | Depend | Validation |\n"
        "| --- | --- | --- | --- | --- | --- | --- |\n"
        + "\n".join(format_lot(lot) for lot in lots)
        + "\n\n"
    )
    return text[:start] + new_body + text[end:]


def lot_map(lots: list[Lot]) -> dict[str, Lot]:
    return {lot.lot_id: lot for lot in lots}


def _normalize_scope_token(token: str) -> str:
    return token.strip().lower()


def machine_name_for_args(args: argparse.Namespace) -> str:
    return (
        args.machine_name
        or os_environ("EXECUTION_MACHINE_NAME")
        or os_environ("MASCARADE_MACHINE_NAME")
        or socket.gethostname().strip()
        or "unknown-machine"
    )


def os_environ(name: str) -> str | None:
    value = os.environ.get(name)
    return value.strip() if value else None


def load_machine_profile(machine_name: str, profiles_path: Path) -> MachineProfile:
    aliases = {machine_name}
    capabilities: set[str] = set()
    if profiles_path.exists():
        payload = json.loads(profiles_path.read_text(encoding="utf-8"))
        machines = payload.get("machines", {})
        for profile_name, profile_data in machines.items():
            raw_aliases = set(profile_data.get("aliases", []))
            raw_aliases.add(profile_name)
            if machine_name == profile_name or machine_name in raw_aliases:
                aliases = {str(item).strip() for item in raw_aliases if str(item).strip()}
                capabilities = {
                    str(item).strip()
                    for item in profile_data.get("capabilities", [])
                    if str(item).strip()
                }
                return MachineProfile(name=profile_name, aliases=aliases, capabilities=capabilities)
    return MachineProfile(name=machine_name, aliases=aliases, capabilities=capabilities)


def load_known_machine_profiles(
    profiles_path: Path,
    *,
    ensure_machine_name: str | None = None,
) -> list[MachineProfile]:
    profiles: list[MachineProfile] = []
    seen_names: set[str] = set()
    if profiles_path.exists():
        payload = json.loads(profiles_path.read_text(encoding="utf-8"))
        machines = payload.get("machines", {})
        for profile_name, profile_data in machines.items():
            aliases = {
                str(item).strip()
                for item in profile_data.get("aliases", [])
                if str(item).strip()
            }
            aliases.add(profile_name)
            capabilities = {
                str(item).strip()
                for item in profile_data.get("capabilities", [])
                if str(item).strip()
            }
            profile = MachineProfile(
                name=profile_name,
                aliases=aliases,
                capabilities=capabilities,
            )
            profiles.append(profile)
            seen_names.add(profile_name)
            seen_names.update(aliases)
    if ensure_machine_name and ensure_machine_name not in seen_names:
        profiles.insert(
            0,
            MachineProfile(
                name=ensure_machine_name,
                aliases={ensure_machine_name},
                capabilities=set(),
            ),
        )
    return profiles


def scope_matches(lot: Lot, profile: MachineProfile, include_foreign: bool = False) -> bool:
    if include_foreign:
        return True
    for token in lot.scope_tokens():
        normalized = _normalize_scope_token(token)
        if normalized in GLOBAL_SCOPES:
            return True
        if normalized.startswith("machine:"):
            target = token.split(":", 1)[1].strip()
            if target == profile.name or target in profile.aliases:
                return True
            continue
        if normalized.startswith("cap:"):
            capability = token.split(":", 1)[1].strip()
            if capability in profile.capabilities:
                return True
            continue
        if token == profile.name or token in profile.aliases or token in profile.capabilities:
            return True
    return False


def relevant_lots(
    lots: list[Lot],
    profile: MachineProfile,
    *,
    include_foreign: bool = False,
) -> list[Lot]:
    return [lot for lot in lots if scope_matches(lot, profile, include_foreign=include_foreign)]


def first_runnable_lot(candidates: list[Lot], all_lots: list[Lot] | None = None) -> Lot | None:
    indexed = lot_map(all_lots or candidates)
    for lot in candidates:
        if lot.status == "IN_PROGRESS":
            return lot
    for lot in candidates:
        if lot.status != "PENDING":
            continue
        if all(indexed.get(dep) and indexed[dep].status == "DONE" for dep in lot.dependencies()):
            return lot
    return None


def pending_lots(candidates: list[Lot], all_lots: list[Lot] | None = None) -> list[Lot]:
    indexed = lot_map(all_lots or candidates)
    ordered: list[Lot] = []
    for lot in candidates:
        if lot.status != "PENDING":
            continue
        if all(indexed.get(dep) and indexed[dep].status == "DONE" for dep in lot.dependencies()):
            ordered.append(lot)
    for lot in candidates:
        if lot.status == "PENDING" and lot not in ordered:
            ordered.append(lot)
    return ordered


def blocked_lots(lots: list[Lot]) -> list[Lot]:
    return [lot for lot in lots if lot.status == "BLOCKED"]


def context_lines(profile: MachineProfile, include_foreign: bool) -> list[str]:
    lines = [f"Machine courante: `{profile.name}`"]
    if profile.capabilities:
        lines.append(f"Capacites: `{profile.display_capabilities()}`")
    if include_foreign:
        lines.append("Vue: `all-scopes`")
    return lines


def refresh_sections(text: str, profile: MachineProfile, include_foreign: bool = False) -> str:
    all_lots = parse_lots(text)
    lots = relevant_lots(all_lots, profile, include_foreign=include_foreign)
    current = [lot for lot in lots if lot.status == "IN_PROGRESS"]
    next_lot = first_runnable_lot(lots, all_lots)
    pending = pending_lots(lots, all_lots)
    blocked = blocked_lots(lots)

    base_lines = context_lines(profile, include_foreign)
    if current:
        current_body = "\n".join(
            base_lines
            + [""]
            + [f"- `{lot.lot_id}` - {lot.title} ({lot.repo})" for lot in current]
        )
    elif next_lot:
        current_body = "\n".join(
            base_lines
            + [
                "",
                "Aucun lot n'est laisse `IN_PROGRESS` a la fin de ce cycle.",
                "",
                "Prochain candidat:",
                f"- `{next_lot.lot_id}` - {next_lot.title} ({next_lot.repo})",
            ]
        )
    elif blocked:
        lines = base_lines + ["", "Aucun lot runnable detecte automatiquement.", "", "Bloquants connus:"]
        lines.extend(f"- `{lot.lot_id}` - {lot.title}" for lot in blocked[:3])
        current_body = "\n".join(lines)
    else:
        current_body = "\n".join(base_lines + ["", "Aucun lot runnable detecte automatiquement."])

    if pending:
        next_body = "\n".join(
            base_lines
            + [""]
            + [
                f"{index}. `{lot.lot_id}` - {lot.title} ({lot.repo})"
                for index, lot in enumerate(pending[:3], start=1)
            ]
        )
    elif blocked:
        next_body = "\n".join(
            base_lines
            + [""]
            + [
                f"{index}. `{lot.lot_id}` - {lot.title} ({lot.repo}) [blocked]"
                for index, lot in enumerate(blocked[:3], start=1)
            ]
        )
    else:
        next_body = "\n".join(base_lines + ["", "1. Aucun lot restant."])

    text = _replace_section(text, "Lot en cours", current_body)
    text = _replace_section(text, "Prochains lots", next_body)
    return text


def append_journal(text: str, message: str) -> str:
    bullet = f"- `{date.today().isoformat()}` - {message}"
    pattern = re.compile(r"(^## Journal d'execution\n)(.*)$", re.MULTILINE | re.DOTALL)
    match = pattern.search(text)
    if not match:
        _fail("section 'Journal d'execution' introuvable")
    body = match.group(2).rstrip()
    if body:
        body = f"{body}\n{bullet}"
    else:
        body = bullet
    return pattern.sub(rf"\1{body}\n", text, count=1)


def get_profile(args: argparse.Namespace) -> MachineProfile:
    return load_machine_profile(machine_name_for_args(args), args.machine_profiles)


def filtered_lots(args: argparse.Namespace) -> tuple[MachineProfile, list[Lot], list[Lot]]:
    profile = get_profile(args)
    all_lots = parse_lots(_load_text(args.hub))
    visible_lots = relevant_lots(all_lots, profile, include_foreign=args.all_scopes)
    return profile, all_lots, visible_lots


def cmd_context(args: argparse.Namespace) -> int:
    profile = get_profile(args)
    payload = {
        "machine": profile.name,
        "aliases": sorted(profile.aliases),
        "capabilities": sorted(profile.capabilities),
        "profiles_path": str(args.machine_profiles),
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=True))
    else:
        print(f"machine: {profile.name}")
        print(f"aliases: {', '.join(sorted(profile.aliases)) or '-'}")
        print(f"capabilities: {profile.display_capabilities()}")
        print(f"profiles_path: {args.machine_profiles}")
    return 0


def cmd_matrix(args: argparse.Namespace) -> int:
    text = _load_text(args.hub)
    all_lots = parse_lots(text)
    machine_name = machine_name_for_args(args)
    profiles = load_known_machine_profiles(
        args.machine_profiles,
        ensure_machine_name=machine_name,
    )
    rows = []
    for profile in profiles:
        visible_lots = relevant_lots(all_lots, profile, include_foreign=args.all_scopes)
        next_lot = first_runnable_lot(visible_lots, all_lots)
        blocked = blocked_lots(visible_lots)
        if next_lot is not None:
            state = "runnable"
        elif blocked:
            state = "blocked"
        else:
            state = "idle"
        rows.append(
            {
                "machine": profile.name,
                "aliases": sorted(profile.aliases),
                "capabilities": sorted(profile.capabilities),
                "state": state,
                "next": next_lot.as_dict() if next_lot else None,
                "blocked_count": len(blocked),
                "blocked_preview": [lot.as_dict() for lot in blocked[:3]],
            }
        )
    if args.json:
        print(json.dumps({"machines": rows}, ensure_ascii=True, indent=2))
    else:
        for row in rows:
            caps = ", ".join(row["capabilities"]) if row["capabilities"] else "-"
            print(f"{row['machine']}\t{row['state']}\t{caps}")
            if row["next"]:
                lot = row["next"]
                print(f"  next: {lot['id']} {lot['title']} ({lot['repo']})")
            elif row["blocked_preview"]:
                first = row["blocked_preview"][0]
                print(f"  blocked: {first['id']} {first['title']}")
            else:
                print("  idle: no matching lots")
    return 0


def cmd_next(args: argparse.Namespace) -> int:
    profile, all_lots, lots = filtered_lots(args)
    lot = first_runnable_lot(lots, all_lots)
    if lot is None:
        payload = {
            "ok": False,
            "machine": profile.name,
            "capabilities": sorted(profile.capabilities),
            "runnable": None,
            "blocked": [row.as_dict() for row in blocked_lots(lots)],
        }
        if args.json:
            print(json.dumps(payload, ensure_ascii=True))
        else:
            print(f"Aucun lot runnable detecte pour {profile.name}.")
            for row in blocked_lots(lots):
                print(f"- {row.lot_id}: {row.title}")
        return 3
    payload = {
        "ok": True,
        "machine": profile.name,
        "capabilities": sorted(profile.capabilities),
        "runnable": lot.as_dict(),
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=True))
    else:
        print(f"{lot.lot_id}\t{lot.repo}\t{lot.title}\t{lot.status}\t{lot.scope}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    profile, all_lots, lots = filtered_lots(args)
    rows = [lot.as_dict() for lot in (all_lots if args.all_scopes else lots)]
    if args.json:
        print(
            json.dumps(
                {
                    "machine": profile.name,
                    "capabilities": sorted(profile.capabilities),
                    "lots": rows,
                },
                ensure_ascii=True,
                indent=2,
            )
        )
    else:
        for row in rows:
            print(
                f"{row['id']}\t{row['status']}\t{row['scope']}\t{row['repo']}\t"
                f"{row['title']}\t{row['depend']}"
            )
    return 0


def cmd_set_status(args: argparse.Namespace) -> int:
    status = args.status.upper()
    if status not in VALID_STATUSES:
        _fail(f"statut invalide: {args.status}")
    text = _load_text(args.hub)
    lots = parse_lots(text)
    updated = False
    for lot in lots:
        if lot.lot_id == args.lot_id:
            lot.status = status
            updated = True
            break
    if not updated:
        _fail(f"lot introuvable: {args.lot_id}")
    text = write_lots(text, lots)
    if args.refresh:
        text = refresh_sections(text, get_profile(args), include_foreign=args.all_scopes)
    if args.journal:
        text = append_journal(text, args.journal)
    args.hub.write_text(text, encoding="utf-8")
    return 0


def cmd_add_lot(args: argparse.Namespace) -> int:
    status = args.status.upper()
    if status not in VALID_STATUSES:
        _fail(f"statut invalide: {args.status}")
    text = _load_text(args.hub)
    lots = parse_lots(text)
    if any(lot.lot_id == args.lot_id for lot in lots):
        _fail(f"lot deja present: {args.lot_id}")
    new_lot = Lot(
        lot_id=args.lot_id,
        repo=args.repo,
        title=args.title,
        status=status,
        scope=args.scope,
        depend=args.depend,
        validation=args.validation,
    )
    if args.after:
        insertion_index = next(
            (index + 1 for index, lot in enumerate(lots) if lot.lot_id == args.after),
            None,
        )
        if insertion_index is None:
            _fail(f"lot de reference introuvable: {args.after}")
        lots.insert(insertion_index, new_lot)
    else:
        lots.append(new_lot)
    text = write_lots(text, lots)
    if args.refresh:
        text = refresh_sections(text, get_profile(args), include_foreign=args.all_scopes)
    if args.journal:
        text = append_journal(text, args.journal)
    args.hub.write_text(text, encoding="utf-8")
    return 0


def cmd_refresh(args: argparse.Namespace) -> int:
    text = _load_text(args.hub)
    refreshed = refresh_sections(text, get_profile(args), include_foreign=args.all_scopes)
    args.hub.write_text(refreshed, encoding="utf-8")
    return 0


def cmd_journal(args: argparse.Namespace) -> int:
    text = _load_text(args.hub)
    updated = append_journal(text, args.message)
    args.hub.write_text(updated, encoding="utf-8")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pilotage du hub d'execution Mascarade")
    parser.add_argument(
        "--hub",
        type=Path,
        default=DEFAULT_HUB,
        help="Chemin du hub markdown",
    )
    parser.add_argument(
        "--machine",
        dest="machine_name",
        help="Nom logique de la machine courante",
    )
    parser.add_argument(
        "--machine-profiles",
        type=Path,
        default=DEFAULT_MACHINE_PROFILES,
        help="Chemin du fichier JSON des profils machine",
    )
    parser.add_argument(
        "--all-scopes",
        action="store_true",
        help="Ignorer le filtrage de portee machine et montrer tous les lots",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    context_parser = sub.add_parser("context", help="Afficher le contexte machine courant")
    context_parser.add_argument("--json", action="store_true")
    context_parser.set_defaults(func=cmd_context)

    next_parser = sub.add_parser("next", help="Afficher le prochain lot runnable")
    next_parser.add_argument("--json", action="store_true")
    next_parser.set_defaults(func=cmd_next)

    matrix_parser = sub.add_parser(
        "matrix", help="Afficher le prochain lot utile par profil machine"
    )
    matrix_parser.add_argument("--json", action="store_true")
    matrix_parser.set_defaults(func=cmd_matrix)

    list_parser = sub.add_parser("list", help="Lister les lots du hub")
    list_parser.add_argument("--json", action="store_true")
    list_parser.set_defaults(func=cmd_list)

    set_parser = sub.add_parser("set-status", help="Mettre a jour le statut d'un lot")
    set_parser.add_argument("--id", dest="lot_id", required=True)
    set_parser.add_argument("--status", required=True)
    set_parser.add_argument("--refresh", action="store_true")
    set_parser.add_argument("--journal", help="Ajouter une ligne de journal")
    set_parser.set_defaults(func=cmd_set_status)

    add_parser = sub.add_parser("add-lot", help="Ajouter un lot au hub")
    add_parser.add_argument("--id", dest="lot_id", required=True)
    add_parser.add_argument("--repo", required=True)
    add_parser.add_argument("--title", required=True)
    add_parser.add_argument("--status", default="PENDING")
    add_parser.add_argument("--scope", default="global")
    add_parser.add_argument("--depend", default="-")
    add_parser.add_argument("--validation", required=True)
    add_parser.add_argument("--after", help="Inserer apres un lot existant")
    add_parser.add_argument("--refresh", action="store_true")
    add_parser.add_argument("--journal", help="Ajouter une ligne de journal")
    add_parser.set_defaults(func=cmd_add_lot)

    refresh_parser = sub.add_parser("refresh", help="Recalculer les sections derivees du hub")
    refresh_parser.set_defaults(func=cmd_refresh)

    journal_parser = sub.add_parser("journal", help="Ajouter une ligne au journal")
    journal_parser.add_argument("--message", required=True)
    journal_parser.set_defaults(func=cmd_journal)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
