from importlib.resources import files
from jinja2 import Environment, FileSystemLoader, select_autoescape


def display(value):
    if value is None or value == "":
        return "Not provided"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def render_report(run):
    env = Environment(loader=FileSystemLoader(str(files("pge_agent") / "templates")),
                      autoescape=select_autoescape(["html"]))
    env.filters["display"] = display
    return env.get_template("report.html").render(run=run,p=run.project,f=run.forecast,
        hour_categories=["Scoping","30% Design","60% Design","90% / IFC","Construction Support","Closeout"],
        milestone_names=["Kickoff / Scoping Complete","30% Design Complete","60% Design Complete",
                         "Permit Package Ready","Permit Submit-By","Long-Lead Material Identification",
                         "Material Order-By","Internal IFC Complete","External Target IFC"])
