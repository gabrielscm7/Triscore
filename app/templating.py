from __future__ import annotations

from fastapi.templating import Jinja2Templates

from app.paths import TEMPLATES_DIR
from app.utils import age_range_label, display_date, mode_label

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.filters["display_date"] = display_date
templates.env.filters["age_range"] = age_range_label
templates.env.filters["mode_label"] = mode_label
templates.env.globals["app_name"] = "Triscore"
