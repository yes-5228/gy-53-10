from flask import Blueprint, request

from ..database import get_connection, rows_to_dicts

spaces_bp = Blueprint("spaces", __name__)


@spaces_bp.get("/", strict_slashes=False)
def list_spaces():
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT s.*,
                CASE
                    WHEN s.status = 'maintenance'
                        AND s.maintenance_end_time IS NOT NULL
                        AND s.maintenance_end_time <= datetime('now', 'localtime')
                    THEN 1 ELSE 0
                END AS maintenance_overdue
            FROM spaces s
            ORDER BY area, code
            """
        ).fetchall()
        stats = conn.execute(
            """
            SELECT status, COUNT(*) AS count
            FROM spaces
            GROUP BY status
            """
        ).fetchall()
        overdue_count = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM spaces
            WHERE status = 'maintenance'
                AND maintenance_end_time IS NOT NULL
                AND maintenance_end_time <= datetime('now', 'localtime')
            """
        ).fetchone()["count"]
    stats_dict = {row["status"]: row["count"] for row in stats}
    stats_dict["maintenance_overdue"] = overdue_count
    return {"items": rows_to_dicts(rows), "stats": stats_dict}


@spaces_bp.patch("/<int:space_id>")
def update_space(space_id):
    data = request.get_json() or {}
    status = data.get("status")
    plate_number = data.get("plate_number")
    maintenance_end_time = data.get("maintenance_end_time")
    allowed = {"free", "occupied", "reserved", "maintenance"}

    if status not in allowed:
        return {"message": "车位状态不合法"}, 400

    with get_connection() as conn:
        if status != "maintenance":
            maintenance_end_time = None
        conn.execute(
            """
            UPDATE spaces
            SET status = ?,
                plate_number = ?,
                maintenance_end_time = ?,
                updated_at = datetime('now', 'localtime')
            WHERE id = ?
            """,
            (
                status,
                plate_number if status == "occupied" else None,
                maintenance_end_time,
                space_id,
            ),
        )
        row = conn.execute(
            """
            SELECT s.*,
                CASE
                    WHEN s.status = 'maintenance'
                        AND s.maintenance_end_time IS NOT NULL
                        AND s.maintenance_end_time <= datetime('now', 'localtime')
                    THEN 1 ELSE 0
                END AS maintenance_overdue
            FROM spaces s
            WHERE s.id = ?
            """,
            (space_id,),
        ).fetchone()

    if not row:
        return {"message": "车位不存在"}, 404
    return dict(row)


@spaces_bp.post("/<int:space_id>/confirm-maintenance", strict_slashes=False)
def confirm_maintenance(space_id):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM spaces WHERE id = ?", (space_id,)
        ).fetchone()
        if not row:
            return {"message": "车位不存在"}, 404
        if row["status"] != "maintenance":
            return {"message": "该车位未处于维护状态"}, 400

        conn.execute(
            """
            UPDATE spaces
            SET status = 'free',
                maintenance_end_time = NULL,
                updated_at = datetime('now', 'localtime')
            WHERE id = ?
            """,
            (space_id,),
        )
        row = conn.execute(
            """
            SELECT s.*,
                CASE
                    WHEN s.status = 'maintenance'
                        AND s.maintenance_end_time IS NOT NULL
                        AND s.maintenance_end_time <= datetime('now', 'localtime')
                    THEN 1 ELSE 0
                END AS maintenance_overdue
            FROM spaces s
            WHERE s.id = ?
            """,
            (space_id,),
        ).fetchone()

    return dict(row)
