from __future__ import annotations

from flask import Blueprint, render_template
from flask_login import login_required

from app.constants import Roles
from app.services.dashboard_service import dashboard_service
from app.utils.decorators import role_required


admin_bp = Blueprint("admin", __name__, template_folder="../templates/admin")


@admin_bp.route("/dashboard")
@login_required
@role_required(Roles.ADMIN)
def dashboard():
  overview = dashboard_service.get_overview()
  return render_template("admin/dashboard.html", overview=overview)

