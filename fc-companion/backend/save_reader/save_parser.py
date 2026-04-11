from __future__ import annotations

import gzip
import json
import shutil
import sqlite3
import subprocess
import tempfile
import zlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


class SaveParser:
    def __init__(self) -> None:
        self.conn: Optional[sqlite3.Connection] = None
        self.save_path: Optional[Path] = None
        self._temp_db_path: Optional[Path] = None
        self.available_tables: List[str] = []
        self.mode: str = "none"
        self.fb_db0: Dict[str, List[Dict[str, Any]]] = {}
        self.fb_db1: Dict[str, List[Dict[str, Any]]] = {}
        self.fb_schema_version: Optional[str] = None

    def _print(self, message: str) -> None:
        print(f"[SaveParser] {message}")

    def _close_temp(self) -> None:
        if self._temp_db_path and self._temp_db_path.exists():
            try:
                self._temp_db_path.unlink()
            except OSError:
                pass
        self._temp_db_path = None

    def close(self) -> None:
        if self.conn is not None:
            self.conn.close()
        self.conn = None
        self.save_path = None
        self.available_tables = []
        self.mode = "none"
        self.fb_db0 = {}
        self.fb_db1 = {}
        self.fb_schema_version = None
        self._close_temp()

    def _try_sqlite_connect(self, db_path: Path) -> sqlite3.Connection:
        return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)

    def _first_16_bytes_hex(self, path: Path) -> str:
        try:
            raw = path.read_bytes()[:16]
            return raw.hex(" ")
        except OSError:
            return "unavailable"

    def _try_decompress_to_temp(self, save_path: Path) -> Optional[Path]:
        raw = save_path.read_bytes()
        strategies = [
            ("gzip", lambda b: gzip.decompress(b)),
            ("zlib", lambda b: zlib.decompress(b)),
        ]
        for name, fn in strategies:
            try:
                decompressed = fn(raw)
                with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
                    tmp.write(decompressed)
                    temp_path = Path(tmp.name)
                self._print(f"Fallback {name} aplicado: {temp_path}")
                return temp_path
            except Exception:
                continue
        return None

    def _headers_map(self, save_path: Path) -> Dict[str, int]:
        try:
            raw = save_path.read_bytes()
        except OSError:
            raw = b""
        return {
            "gzip": raw.find(b"\x1f\x8b\x08"),
            "zlib_9c": raw.find(b"\x78\x9c"),
            "zlib_da": raw.find(b"\x78\xda"),
            "zlib_01": raw.find(b"\x78\x01"),
            "sqlite": raw.find(b"SQLite format 3\x00"),
            "fbchunks": raw.find(b"FBCHUNKS"),
        }

    def _fb_tables(self) -> List[str]:
        out = [f"db0.{t}" for t in self.fb_db0.keys()]
        out.extend([f"db1.{t}" for t in self.fb_db1.keys()])
        return sorted(out)

    def _fb_get_table(self, table: str, preferred_db: Optional[int] = None) -> List[Dict[str, Any]]:
        if preferred_db == 0:
            return self.fb_db0.get(table, [])
        if preferred_db == 1:
            return self.fb_db1.get(table, [])
        if table in self.fb_db0:
            return self.fb_db0.get(table, [])
        return self.fb_db1.get(table, [])

    def _table_exists(self, table: str) -> bool:
        if self.mode == "fbchunks":
            return table in self.fb_db0 or table in self.fb_db1
        return table in self.available_tables

    def _table_columns(self, table: str) -> List[str]:
        if self.mode == "fbchunks":
            rows = self._fb_get_table(table)
            if not rows:
                return []
            return list(rows[0].keys())
        if self.conn is None:
            return []
        try:
            cur = self.conn.execute(f"PRAGMA table_info({table})")
            return [str(row[1]) for row in cur.fetchall()]
        except sqlite3.Error:
            return []

    def _table_row_count(self, table: str) -> int:
        if self.mode == "fbchunks":
            return len(self._fb_get_table(table))
        rows = self._execute(f"SELECT COUNT(*) AS total FROM {table}")
        if not rows:
            return 0
        try:
            return int(rows[0]["total"])
        except (TypeError, ValueError, KeyError):
            return 0

    def get_table_catalog(self) -> List[Dict[str, Any]]:
        return [{"table": full_name} for full_name in self.available_tables]

    def get_finance_table_candidates(self) -> List[Dict[str, Any]]:
        hints: Dict[str, List[str]] = {
            "career_managerpref": [
                "transferbudget",
                "wagebudget",
                "startofseasontransferbudget",
                "startofseasonwagebudget",
            ],
            "career_managerinfo": [
                "totalearnings",
                "wage",
            ],
            "career_managerhistory": [
                "bigbuyamount",
                "bigsellamount",
                "bigbuyplayername",
                "bigsellplayername",
            ],
            "career_playercontract": [
                "wage",
                "signon_bonus",
                "performancebonusvalue",
                "performancebonuscount",
            ],
            "career_users": [
                "wage",
                "seasoncount",
            ],
            "teams": [
                "clubworth",
                "transferbudget",
                "teamid",
                "teamname",
            ],
        }
        out: List[Dict[str, Any]] = []
        for table_name, column_hits in hints.items():
            if self._table_exists(table_name):
                out.append(
                    {
                        "table": table_name,
                        "column_hits": column_hits,
                    }
                )
        return out

    def _execute(self, query: str, params: Sequence[Any] = ()) -> List[sqlite3.Row]:
        if self.mode != "sqlite":
            return []
        if self.conn is None:
            return []
        try:
            cur = self.conn.execute(query, params)
            return cur.fetchall()
        except sqlite3.Error as exc:
            self._print(f"Query falhou: {exc}")
            return []

    def _is_sqlite_ready(self) -> bool:
        rows = self._execute("SELECT name FROM sqlite_master WHERE type='table'")
        self.available_tables = [str(row["name"]) for row in rows]
        if not self.available_tables:
            return False
        probe = self._execute("SELECT 1")
        return bool(probe)

    def _ensure_fb_parser_ready(self) -> Tuple[Path, Path, Path]:
        node_path = shutil.which("node")
        if not node_path:
            raise RuntimeError("Node.js não encontrado no sistema")
        npm_path = shutil.which("npm")
        if not npm_path:
            raise RuntimeError("npm não encontrado no sistema")
        parser_dir = Path(__file__).resolve().parent / "node_fbparser"
        script_path = parser_dir / "parse_fbchunks.js"
        dep_path = parser_dir / "node_modules" / "fifa-career-save-parser"
        if not dep_path.exists():
            install = subprocess.run(
                [npm_path, "install", "fifa-career-save-parser", "--silent"],
                cwd=str(parser_dir),
                check=False,
                timeout=240,
                capture_output=True,
                text=True,
            )
            if install.returncode != 0:
                raise RuntimeError(
                    f"npm install falhou: {install.stderr or install.stdout or install.returncode}"
                )
        return Path(node_path), script_path, dep_path

    def _connect_fbchunks(self, save_path: Path) -> bool:
        try:
            node_path, script_path, parser_cwd = self._ensure_fb_parser_ready()
        except Exception as exc:
            self._print(f"Falha preparando parser FBCHUNKS: {exc}")
            return False
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
            out_json_path = Path(tmp.name)
        try:
            subprocess.run(
                [str(node_path), str(script_path), str(save_path), str(out_json_path)],
                check=True,
                timeout=240,
                capture_output=True,
                text=True,
                cwd=str(parser_cwd),
            )
            payload = json.loads(out_json_path.read_text(encoding="utf-8"))
            self.fb_db0 = payload.get("db0") or {}
            self.fb_db1 = payload.get("db1") or {}
            self.fb_schema_version = str(payload.get("version") or "")
            self.mode = "fbchunks"
            self.available_tables = self._fb_tables()
            self._print(
                f"FBCHUNKS carregado. schema={self.fb_schema_version} tabelas={len(self.available_tables)}"
            )
            return bool(self.available_tables)
        except subprocess.CalledProcessError as exc:
            self._print(f"Falha no parser FBCHUNKS: {exc.stderr or exc.stdout or exc}")
            return False
        except Exception as exc:
            self._print(f"Falha no decode FBCHUNKS: {exc}")
            return False
        finally:
            try:
                out_json_path.unlink(missing_ok=True)
            except OSError:
                pass

    def _row_get(self, row: Dict[str, Any], *keys: str, default: Any = None) -> Any:
        for key in keys:
            if key in row and row[key] is not None:
                return row[key]
        return default

    def _to_int(self, value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _to_float(self, value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _fb_merge_rows_two_dbs(self, table: str, id_field: str) -> Dict[int, Dict[str, Any]]:
        """Une linhas de db0 e db1; campos não-nulos de qualquer lado preenchem lacunas."""
        merged: Dict[int, Dict[str, Any]] = {}
        for rows in (self.fb_db0.get(table) or [], self.fb_db1.get(table) or []):
            for row in rows:
                rid = self._to_int(row.get(id_field), -1)
                if rid < 0:
                    continue
                if rid not in merged:
                    merged[rid] = dict(row)
                    continue
                base = merged[rid]
                for k, v in row.items():
                    if v is None:
                        continue
                    if k not in base or base[k] is None or base[k] == "":
                        base[k] = v
        return merged

    def _fb_name_map_two_dbs(self) -> Dict[int, str]:
        out: Dict[int, str] = {}
        for rows in (self.fb_db0.get("dcplayernames") or [], self.fb_db1.get("dcplayernames") or []):
            for n in rows:
                nid = self._to_int(n.get("nameid"), -1)
                if nid < 0:
                    continue
                name = str(n.get("name") or "").strip()
                if name:
                    out[nid] = name
        return out

    def _squadranking_overall_to_float(self, raw: Any) -> Optional[float]:
        """curroverall/lastoverall: em vários saves vem ×10 (ex. 840); noutros já 0–100."""
        if raw is None:
            return None
        v = self._to_float(raw, -1.0)
        if v < 0:
            return None
        if v > 100:
            return v / 10.0
        return v

    def _fb_contracts_for_team(self, user_team_id: int) -> List[Dict[str, Any]]:
        """Contratos do clube em db0+db1; uma linha por playerid (campos fundidos)."""
        by_pid: Dict[int, Dict[str, Any]] = {}
        for rows in (self.fb_db0.get("career_playercontract") or [], self.fb_db1.get("career_playercontract") or []):
            for c in rows:
                if self._to_int(c.get("teamid")) != user_team_id:
                    continue
                pid = self._to_int(c.get("playerid"), -1)
                if pid < 0:
                    continue
                if pid not in by_pid:
                    by_pid[pid] = dict(c)
                else:
                    base = by_pid[pid]
                    for k, v in c.items():
                        if v is not None and (k not in base or base[k] is None):
                            base[k] = v
        return list(by_pid.values())

    def _resolve_fb_name(
        self,
        player_row: Dict[str, Any],
        edited_row: Optional[Dict[str, Any]],
        names_by_id: Dict[int, str],
    ) -> Tuple[str, str, str]:
        if edited_row:
            first = str(self._row_get(edited_row, "firstname", default="") or "").strip()
            last = str(self._row_get(edited_row, "surname", "lastname", default="") or "").strip()
            common = str(self._row_get(edited_row, "commonname", default="") or "").strip()
            return first, last, common
        fid = self._to_int(self._row_get(player_row, "firstnameid", default=0))
        lid = self._to_int(self._row_get(player_row, "lastnameid", default=0))
        cid = self._to_int(self._row_get(player_row, "commonnameid", default=0))
        first = str(names_by_id.get(fid, "") or "").strip()
        last = str(names_by_id.get(lid, "") or "").strip()
        common = str(names_by_id.get(cid, "") or "").strip()
        return first, last, common

    def _build_player_name(self, row: Dict[str, Any]) -> Tuple[str, str]:
        common = str(row.get("commonname") or "").strip()
        first = str(row.get("firstname") or "").strip()
        last = str(row.get("lastname") or "").strip()
        full = " ".join(x for x in [first, last] if x).strip()
        name = common or full
        source = "save_commonname" if common else ("save_first_last" if full else "unresolved")
        return name, source

    def _normalize_squad(self, squad: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[int]]:
        unresolved_ids: List[int] = []
        out: List[Dict[str, Any]] = []
        for row in squad:
            playerid = self._to_int(row.get("playerid"), 0)
            name, source = self._build_player_name(row)
            if not name:
                unresolved_ids.append(playerid)
                name = f"ID {playerid}"
            normalized = dict(row)
            normalized["playerid"] = playerid
            normalized["player_name"] = name
            normalized["name_source"] = source
            out.append(normalized)
        seen = set()
        unique_unresolved = []
        for pid in unresolved_ids:
            if pid <= 0 or pid in seen:
                continue
            seen.add(pid)
            unique_unresolved.append(pid)
        return out, unique_unresolved

    def connect(self, save_path: Path) -> bool:
        self.close()
        self.save_path = save_path
        headers = self._headers_map(save_path)
        if headers.get("fbchunks", -1) >= 0 and self._connect_fbchunks(save_path):
            return True
        self._print(f"Header (16 bytes): {self._first_16_bytes_hex(save_path)}")
        self._print(f"Assinaturas detectadas: {headers}")
        self._print("Save fora do padrão FBCHUNKS. Leitura cancelada.")
        self.close()
        return False

    def get_squad(self, user_team_id: int) -> List[Dict[str, Any]]:
        if self.mode == "fbchunks":
            contracts = self._fb_contracts_for_team(user_team_id)
            players_by_id = self._fb_merge_rows_two_dbs("players", "playerid")
            edited_by_pid = self._fb_merge_rows_two_dbs("editedplayernames", "playerid")
            names_by_id = self._fb_name_map_two_dbs()
            team_links_all = (self.fb_db0.get("teamplayerlinks") or []) + (
                self.fb_db1.get("teamplayerlinks") or []
            )
            links_by_pid: Dict[int, Dict[str, Any]] = {}
            for t in team_links_all:
                if self._to_int(t.get("teamid")) != user_team_id or t.get("playerid") is None:
                    continue
                pid = self._to_int(t.get("playerid"))
                if pid not in links_by_pid:
                    links_by_pid[pid] = dict(t)
                else:
                    base = links_by_pid[pid]
                    for k, v in t.items():
                        if v is not None and (k not in base or base[k] is None):
                            base[k] = v
            rank_by_pid = self._fb_merge_rows_two_dbs("career_squadranking", "playerid")
            growth_by_pid = self._fb_merge_rows_two_dbs("career_playergrowthuserseason", "playerid")
            out: List[Dict[str, Any]] = []
            for c in contracts:
                pid = self._to_int(c.get("playerid"))
                p = players_by_id.get(pid, {})
                e = edited_by_pid.get(pid)
                first, last, common = self._resolve_fb_name(p, e, names_by_id)
                rank = rank_by_pid.get(pid, {})
                growth = growth_by_pid.get(pid, {})
                link = links_by_pid.get(pid, {})
                overall_raw = self._row_get(p, "overallrating", default=None)
                overall_live_raw = self._row_get(rank, "curroverall", default=None)
                overall_live = self._squadranking_overall_to_float(overall_live_raw)
                last_over_raw = self._row_get(rank, "lastoverall", default=None)
                overall_prev = self._squadranking_overall_to_float(last_over_raw)
                row = {
                    "playerid": pid,
                    "firstname": first,
                    "lastname": last,
                    "commonname": common,
                    "overallrating": overall_raw,
                    "overall_live": overall_live,
                    "overall_prev": overall_prev,
                    "potential": self._row_get(p, "potential", default=self._row_get(growth, "potential")),
                    "age": self._row_get(p, "age"),
                    "birthdate": self._row_get(p, "birthdate"),
                    "preferredposition1": self._row_get(p, "preferredposition1"),
                    "nationality": self._row_get(p, "nationality"),
                    "value": self._row_get(p, "value"),
                    "wage": self._row_get(p, "wage"),
                    "morale": self._row_get(p, "morale"),
                    "form": self._row_get(link, "form", default=self._row_get(p, "form")),
                    "sharpness": self._row_get(p, "sharpness"),
                    "fitness": self._row_get(p, "fitness"),
                    "contractvaliduntil": self._row_get(c, "contractvaliduntil"),
                    "contract_wage": self._row_get(c, "wage"),
                    "signon_bonus": self._row_get(c, "signon_bonus"),
                    "performancebonusvalue": self._row_get(c, "performancebonusvalue"),
                    "performancebonuscount": self._row_get(c, "performancebonuscount"),
                    "performancebonuscountachieved": self._row_get(c, "performancebonuscountachieved"),
                    "isperformancebonusachieved": self._row_get(c, "isperformancebonusachieved"),
                    "playerrole": self._row_get(c, "playerrole"),
                    "jerseynumber": self._row_get(link, "jerseynumber"),
                }
                out.append(row)
            out.sort(
                key=lambda r: (
                    r.get("overall_live") is None and r.get("overallrating") is None,
                    -(self._to_float(r.get("overall_live"), self._to_float(r.get("overallrating"), 0.0))),
                    -self._to_float(r.get("contract_wage"), 0.0),
                )
            )
            return out
        if not self._table_exists("career_playercontract"):
            return []
        if self._table_exists("players"):
            query = """
                SELECT
                  p.playerid, p.firstname, p.lastname, p.commonname,
                  p.overallrating, p.potential, p.age, p.birthdate,
                  p.preferredposition1, p.nationality, p.value, p.wage,
                  p.morale, p.form, p.sharpness, p.fitness,
                  c.contractvaliduntil, c.wage AS contract_wage, c.playerrole,
                  c.signon_bonus, c.performancebonusvalue, c.performancebonuscount,
                  c.performancebonuscountachieved, c.isperformancebonusachieved
                FROM players p
                LEFT JOIN career_playercontract c ON p.playerid = c.playerid
                WHERE c.teamid = ?
                ORDER BY p.overallrating DESC
            """
            rows = self._execute(query, (user_team_id,))
            return [dict(r) for r in rows]
        query = """
            SELECT
              c.playerid,
              c.contractvaliduntil, c.wage AS contract_wage, c.playerrole,
              c.signon_bonus, c.performancebonusvalue, c.performancebonuscount,
              c.performancebonuscountachieved, c.isperformancebonusachieved
            FROM career_playercontract c
            WHERE c.teamid = ?
            ORDER BY c.wage DESC
        """
        rows = self._execute(query, (user_team_id,))
        return [dict(r) for r in rows]

    def get_injuries(self) -> List[Dict[str, Any]]:
        if self.mode == "fbchunks":
            if self._table_exists("career_injuries"):
                return list(self._fb_get_table("career_injuries", preferred_db=0))
            return []
        if not self._table_exists("career_injuries"):
            return []
        if not self._table_exists("players"):
            query = "SELECT * FROM career_injuries"
            return [dict(r) for r in self._execute(query)]
        query = """
            SELECT i.*, p.commonname, p.firstname, p.lastname
            FROM career_injuries i
            JOIN players p ON i.playerid = p.playerid
        """
        return [dict(r) for r in self._execute(query)]

    def get_transfer_offers(self) -> List[Dict[str, Any]]:
        if self.mode == "fbchunks":
            if not self._table_exists("career_transferoffer"):
                return []
            return list(self._fb_get_table("career_transferoffer", preferred_db=0))
        if not self._table_exists("career_transferoffer"):
            return []
        if not self._table_exists("players"):
            return [dict(r) for r in self._execute("SELECT * FROM career_transferoffer")]
        has_teams = self._table_exists("teams")
        if has_teams:
            query = """
                SELECT t.*,
                  p.commonname AS player_name,
                  p.overallrating,
                  src.teamname AS from_team_name
                FROM career_transferoffer t
                JOIN players p ON t.playerid = p.playerid
                LEFT JOIN teams src ON t.fromteamid = src.teamid
            """
        else:
            query = """
                SELECT t.*,
                  p.commonname AS player_name,
                  p.overallrating,
                  NULL AS from_team_name
                FROM career_transferoffer t
                JOIN players p ON t.playerid = p.playerid
            """
        return [dict(r) for r in self._execute(query)]

    def get_transfer_history(self, user_team_id: int) -> List[Dict[str, Any]]:
        def period_from_raw(raw_value: Any) -> str:
            value = self._to_int(raw_value, 0)
            if value <= 0:
                return ""
            year = value // 10000
            month = (value % 10000) // 100
            if year <= 0 or month <= 0 or month > 12:
                return ""
            return f"{year:04d}-{month:02d}"

        def row_counts_as_transfer(
            amount: float,
            is_loan_buy: int,
            complete_date: int,
            signed_date: int,
        ) -> bool:
            """Alinhado ao companion_export.lua: grátis / empréstimo com datas contam."""
            if amount > 0:
                return True
            if is_loan_buy != 0:
                return True
            if complete_date > 0 or signed_date > 0:
                return True
            return False

        if self.mode == "fbchunks":
            if not self._table_exists("career_presignedcontract"):
                return []
            rows = list(self._fb_get_table("career_presignedcontract", preferred_db=0))
            players = self._fb_get_table("players", preferred_db=1)
            teams = self._fb_get_table("teams", preferred_db=1)
            player_name_by_id = {}
            for player in players:
                pid = self._to_int(player.get("playerid"), 0)
                if pid <= 0:
                    continue
                common = str(player.get("commonname") or "").strip()
                first = str(player.get("firstname") or "").strip()
                last = str(player.get("lastname") or "").strip()
                name = common or f"{first} {last}".strip() or f"Jogador {pid}"
                player_name_by_id[pid] = name
            team_name_by_id = {self._to_int(team.get("teamid"), 0): str(team.get("teamname") or "") for team in teams}
            out: List[Dict[str, Any]] = []
            seen = set()
            for row in rows:
                offer_team_id = self._to_int(row.get("offerteamid"), 0)
                source_team_id = self._to_int(row.get("teamid"), 0)
                player_id = self._to_int(row.get("playerid"), 0)
                signed_date = self._to_int(row.get("signeddate"), 0)
                complete_date = self._to_int(row.get("completedate"), 0)
                offered_fee = self._to_float(row.get("offeredfee"), 0.0)
                future_fee = self._to_float(row.get("future_fee"), 0.0)
                amount = offered_fee if offered_fee > 0 else future_fee
                is_loan_buy = self._to_int(row.get("isloanbuy"), 0)
                is_buy = offer_team_id == user_team_id and source_team_id > 0 and source_team_id != user_team_id
                is_sell = source_team_id == user_team_id and offer_team_id > 0 and offer_team_id != user_team_id
                if (not is_buy and not is_sell) or not row_counts_as_transfer(
                    float(amount), is_loan_buy, complete_date, signed_date
                ):
                    continue
                key = (player_id, signed_date, source_team_id, offer_team_id, int(amount))
                if key in seen:
                    continue
                seen.add(key)
                from_team_id = source_team_id if is_buy else user_team_id
                to_team_id = offer_team_id
                out.append(
                    {
                        "id": f"presigned:{player_id}:{signed_date}:{source_team_id}:{offer_team_id}:{int(amount)}",
                        "player_id": player_id,
                        "player_name": player_name_by_id.get(player_id, f"Jogador {player_id}"),
                        "amount": round(amount, 2),
                        "fee": round(amount, 2),
                        "type": "buy" if is_buy else "sell",
                        "direction": "in" if is_buy else "out",
                        "is_loan_buy": is_loan_buy,
                        "signed_date": signed_date,
                        "completed_date": complete_date,
                        "period": period_from_raw(signed_date) or period_from_raw(complete_date),
                        "from_team_id": from_team_id,
                        "from_team_name": team_name_by_id.get(from_team_id, ""),
                        "to_team_id": to_team_id,
                        "to_team_name": team_name_by_id.get(to_team_id, ""),
                        "source": "career_presignedcontract",
                    }
                )
            out.sort(key=lambda item: (self._to_int(item.get("signed_date"), 0), str(item.get("id"))))
            return out

        if not self._table_exists("career_presignedcontract"):
            return []
        if self._table_exists("players") and self._table_exists("teams"):
            rows = self._execute(
                """
                SELECT c.*, p.commonname, p.firstname, p.lastname,
                       src.teamname AS source_team_name, dst.teamname AS offer_team_name
                FROM career_presignedcontract c
                LEFT JOIN players p ON c.playerid = p.playerid
                LEFT JOIN teams src ON c.teamid = src.teamid
                LEFT JOIN teams dst ON c.offerteamid = dst.teamid
                """
            )
        else:
            rows = self._execute("SELECT * FROM career_presignedcontract")
        out: List[Dict[str, Any]] = []
        seen = set()
        for row_obj in rows:
            row = dict(row_obj)
            offer_team_id = self._to_int(row.get("offerteamid"), 0)
            source_team_id = self._to_int(row.get("teamid"), 0)
            player_id = self._to_int(row.get("playerid"), 0)
            signed_date = self._to_int(row.get("signeddate"), 0)
            complete_date = self._to_int(row.get("completedate"), 0)
            offered_fee = self._to_float(row.get("offeredfee"), 0.0)
            future_fee = self._to_float(row.get("future_fee"), 0.0)
            amount = offered_fee if offered_fee > 0 else future_fee
            is_loan_buy = self._to_int(row.get("isloanbuy"), 0)
            is_buy = offer_team_id == user_team_id and source_team_id > 0 and source_team_id != user_team_id
            is_sell = source_team_id == user_team_id and offer_team_id > 0 and offer_team_id != user_team_id
            if (not is_buy and not is_sell) or not row_counts_as_transfer(
                float(amount), is_loan_buy, complete_date, signed_date
            ):
                continue
            key = (player_id, signed_date, source_team_id, offer_team_id, int(amount))
            if key in seen:
                continue
            seen.add(key)
            player_name = str(row.get("commonname") or "").strip()
            if not player_name:
                player_name = f"{str(row.get('firstname') or '').strip()} {str(row.get('lastname') or '').strip()}".strip() or f"Jogador {player_id}"
            from_team_id = source_team_id if is_buy else user_team_id
            to_team_id = offer_team_id
            out.append(
                {
                    "id": f"presigned:{player_id}:{signed_date}:{source_team_id}:{offer_team_id}:{int(amount)}",
                    "player_id": player_id,
                    "player_name": player_name,
                    "amount": round(amount, 2),
                    "fee": round(amount, 2),
                    "type": "buy" if is_buy else "sell",
                    "direction": "in" if is_buy else "out",
                    "is_loan_buy": is_loan_buy,
                    "signed_date": signed_date,
                    "completed_date": complete_date,
                    "period": period_from_raw(signed_date) or period_from_raw(complete_date),
                    "from_team_id": from_team_id,
                    "from_team_name": row.get("source_team_name") or "",
                    "to_team_id": to_team_id,
                    "to_team_name": row.get("offer_team_name") or "",
                    "source": "career_presignedcontract",
                }
            )
        out.sort(key=lambda item: (self._to_int(item.get("signed_date"), 0), str(item.get("id"))))
        return out

    def get_manager_data(self) -> Dict[str, Any]:
        if self.mode == "fbchunks":
            users = self._fb_get_table("career_users", preferred_db=0)
            manager = dict(users[0]) if users else {}
            manager_info_rows = self._fb_get_table("career_managerinfo", preferred_db=0)
            manager_pref_rows = self._fb_get_table("career_managerpref", preferred_db=0)
            manager_history_rows = self._fb_get_table("career_managerhistory", preferred_db=0)
            if manager_info_rows:
                manager["manager_info"] = manager_info_rows[0]
            if manager_pref_rows:
                manager["manager_pref"] = manager_pref_rows[0]
            if manager_history_rows:
                manager["manager_history"] = manager_history_rows[0]
            return manager
        if not self._table_exists("career_users"):
            return {}
        rows = self._execute("SELECT * FROM career_users LIMIT 1")
        manager = dict(rows[0]) if rows else {}
        if self._table_exists("career_managerinfo"):
            info_rows = self._execute("SELECT * FROM career_managerinfo LIMIT 1")
            if info_rows:
                manager["manager_info"] = dict(info_rows[0])
        if self._table_exists("career_managerpref"):
            pref_rows = self._execute("SELECT * FROM career_managerpref LIMIT 1")
            if pref_rows:
                manager["manager_pref"] = dict(pref_rows[0])
        if self._table_exists("career_managerhistory"):
            history_rows = self._execute("SELECT * FROM career_managerhistory LIMIT 1")
            if history_rows:
                manager["manager_history"] = dict(history_rows[0])
        return manager

    def get_all_teams(self) -> List[Dict[str, Any]]:
        if self.mode == "fbchunks":
            teams = self._fb_get_table("teams", preferred_db=1)
            out = []
            for t in teams:
                out.append(
                    {
                        "teamid": self._row_get(t, "teamid"),
                        "teamname": self._row_get(t, "teamname"),
                        "overallrating": self._row_get(t, "overallrating"),
                        "attackrating": self._row_get(t, "attackrating"),
                        "midfieldrating": self._row_get(t, "midfieldrating"),
                        "defencerating": self._row_get(t, "defencerating"),
                        "clubworth": self._row_get(t, "clubworth"),
                        "transferbudget": self._row_get(t, "transferbudget"),
                    }
                )
            return out
        if not self._table_exists("teams"):
            return []
        if not self._table_exists("career_calendar"):
            query = """
                SELECT teamid, teamname, overallrating,
                       attackrating, midfieldrating, defencerating
                FROM teams
            """
            return [dict(r) for r in self._execute(query)]
        query = """
            SELECT teamid, teamname, overallrating,
                   attackrating, midfieldrating, defencerating
            FROM teams
            WHERE teamid IN (
              SELECT DISTINCT hometeamid FROM career_calendar
            )
        """
        return [dict(r) for r in self._execute(query)]

    def get_season_stats(self) -> Dict[str, Any]:
        stats = {
            "matches": 0,
            "wins": 0,
            "draws": 0,
            "losses": 0,
            "goals_for": 0,
            "goals_against": 0,
            "top_scorer": {},
            "top_assist": {},
        }
        if self.mode == "fbchunks":
            users = self._fb_get_table("career_users", preferred_db=0)
            user_team_id = self._to_int((users[0] if users else {}).get("clubteamid"), -1)
            links = self._fb_get_table("teamplayerlinks", preferred_db=1)
            squad_links = [r for r in links if self._to_int(r.get("teamid"), -1) == user_team_id]
            stats["matches"] = max(
                (self._to_int(self._row_get(r, "leagueappearances", default=0)) for r in squad_links),
                default=0,
            )
            stats["goals_for"] = sum(self._to_int(self._row_get(r, "leaguegoals", default=0)) for r in squad_links)
            top_goal_row = None
            top_goal = -1
            top_assist_row = None
            top_assist = -1
            for row in squad_links:
                goals = self._to_int(self._row_get(row, "leaguegoals", default=0))
                assists = self._to_int(self._row_get(row, "leagueassists", "assists", default=0))
                if goals > top_goal:
                    top_goal = goals
                    top_goal_row = row
                if assists > top_assist:
                    top_assist = assists
                    top_assist_row = row
            if top_goal_row is not None:
                stats["top_scorer"] = {
                    "playerid": self._to_int(top_goal_row.get("playerid")),
                    "total_goals": top_goal,
                }
            if top_assist_row is not None:
                stats["top_assist"] = {
                    "playerid": self._to_int(top_assist_row.get("playerid")),
                    "total_assists": top_assist,
                }
            manager_hist = self._fb_get_table("career_managerhistory", preferred_db=0)
            if manager_hist:
                row = manager_hist[0]
                stats["wins"] = self._to_int(self._row_get(row, "wins", default=0))
                stats["draws"] = self._to_int(self._row_get(row, "draws", default=0))
                stats["losses"] = self._to_int(self._row_get(row, "losses", default=0))
            return stats
        if self._table_exists("career_calendar"):
            cols = set(self._table_columns("career_calendar"))
            home_goals_col = "homescore" if "homescore" in cols else None
            away_goals_col = "awayscore" if "awayscore" in cols else None
            if home_goals_col and away_goals_col:
                rows = self._execute(
                    f"""
                    SELECT
                      COUNT(*) AS matches,
                      SUM(CASE WHEN {home_goals_col} > {away_goals_col} THEN 1 ELSE 0 END) AS wins,
                      SUM(CASE WHEN {home_goals_col} = {away_goals_col} THEN 1 ELSE 0 END) AS draws,
                      SUM(CASE WHEN {home_goals_col} < {away_goals_col} THEN 1 ELSE 0 END) AS losses,
                      SUM({home_goals_col}) AS goals_for,
                      SUM({away_goals_col}) AS goals_against
                    FROM career_calendar
                    WHERE {home_goals_col} IS NOT NULL AND {away_goals_col} IS NOT NULL
                    """
                )
                if rows:
                    row = dict(rows[0])
                    stats["matches"] = int(row.get("matches") or 0)
                    stats["wins"] = int(row.get("wins") or 0)
                    stats["draws"] = int(row.get("draws") or 0)
                    stats["losses"] = int(row.get("losses") or 0)
                    stats["goals_for"] = int(row.get("goals_for") or 0)
                    stats["goals_against"] = int(row.get("goals_against") or 0)

        if self._table_exists("career_playerstats"):
            cols = set(self._table_columns("career_playerstats"))
            goal_col = "goals" if "goals" in cols else None
            assist_col = "assists" if "assists" in cols else None
            if goal_col:
                rows = self._execute(
                    f"""
                    SELECT playerid, {goal_col} AS total_goals
                    FROM career_playerstats
                    ORDER BY {goal_col} DESC
                    LIMIT 1
                    """
                )
                if rows:
                    stats["top_scorer"] = dict(rows[0])
            if assist_col:
                rows = self._execute(
                    f"""
                    SELECT playerid, {assist_col} AS total_assists
                    FROM career_playerstats
                    ORDER BY {assist_col} DESC
                    LIMIT 1
                    """
                )
                if rows:
                    stats["top_assist"] = dict(rows[0])
        return stats

    def extract_all(self, user_team_id: int) -> Dict[str, Any]:
        def guard_list(fn):
            try:
                return fn()
            except Exception as exc:
                self._print(f"Falha em {fn.__name__}: {exc}")
                return []

        def guard_dict(fn):
            try:
                return fn()
            except Exception as exc:
                self._print(f"Falha em {fn.__name__}: {exc}")
                return {}

        squad_raw = guard_list(lambda: self.get_squad(user_team_id))
        squad, unresolved_name_player_ids = self._normalize_squad(squad_raw)
        return {
            "squad": squad,
            "injuries": guard_list(self.get_injuries),
            "transfer_offers": guard_list(self.get_transfer_offers),
            "transfer_history": guard_list(lambda: self.get_transfer_history(user_team_id)),
            "manager": guard_dict(self.get_manager_data),
            "teams": guard_list(self.get_all_teams),
            "season_stats": guard_dict(self.get_season_stats),
            "unresolved_name_player_ids": unresolved_name_player_ids,
            "source": "save_file",
            "mode": self.mode,
            "schema_version": self.fb_schema_version,
            "finance_table_candidates": guard_list(self.get_finance_table_candidates),
            "extracted_at": datetime.now().isoformat(),
        }
