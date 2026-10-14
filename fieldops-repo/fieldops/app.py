# app.py - FieldOps web screen for the dispatch desk
from flask import Flask, request, redirect
from fieldops import store, assign, report

app = Flask(__name__)
PORT = 8077

HEAD = "<html><head><title>FieldOps</title></head><body>"
HEAD = HEAD + "<h2>FieldOps - Sequoia Power &amp; Light</h2>"
HEAD = HEAD + "<p><a href='/'>Orders</a> | <a href='/report'>Daily report</a></p>"
FOOT = "</body></html>"


def esc(s):
    s = str(s)
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("'", "&#39;")


@app.route("/")
def index():
    html = HEAD + "<table border='1' cellpadding='4'>"
    html = html + "<tr><th>ID</th><th>Site</th><th>Equipment</th><th>Description</th>"
    html = html + "<th>Priority</th><th>Status</th><th>Crew</th><th></th></tr>"
    for o in store.load_orders():
        if o["status"] not in ("open", "assigned"):
            continue
        html = html + "<tr><td>" + str(o["id"]) + "</td><td>" + esc(o["site"]) + "</td>"
        html = html + "<td>" + esc(o["equipment"]) + "</td><td>" + esc(o["description"]) + "</td>"
        html = html + "<td>" + str(o["priority"]) + "</td><td>" + o["status"] + "</td>"
        html = html + "<td>" + esc(o["crew"]) + "</td>"
        html = html + "<td><a href='/assign/" + str(o["id"]) + "'>assign</a></td></tr>"
    return html + "</table>" + FOOT


@app.route("/assign/<int:order_id>", methods=["GET", "POST"])
def assign_page(order_id):
    o = store.get_order(order_id)
    if o is None:
        return HEAD + "<p>No such order.</p>" + FOOT, 404
    if request.method == "POST":
        if assign.assign_order(order_id, request.form.get("crew", "")):
            return redirect("/")
        return HEAD + "<p>Could not assign order " + str(order_id) + ".</p>" + FOOT, 400
    html = HEAD + "<h3>Order " + str(o["id"]) + ": " + esc(o["description"]) + "</h3>"
    html = html + "<p>" + esc(o["site"]) + " / " + esc(o["equipment"]) + " / P" + str(o["priority"]) + "</p>"
    html = html + "<form method='post'><select name='crew'>"
    for c in store.load_crews():
        sel = " selected" if c["id"] == o["crew"] else ""
        html = html + "<option value='" + c["id"] + "'" + sel + ">" + c["id"] + " - " + esc(c["name"]) + "</option>"
    html = html + "</select> <input type='submit' value='Assign'></form>"
    html = html + "<form method='post' action='/close/" + str(o["id"]) + "'>"
    html = html + "<input type='submit' value='Close order'></form>"
    return html + FOOT


@app.route("/close/<int:order_id>", methods=["POST"])
def close(order_id):
    if store.update_order(order_id, status="closed") is None:
        return HEAD + "<p>No such order.</p>" + FOOT, 404
    return redirect("/")


@app.route("/report")
def report_page():
    return HEAD + "<pre>" + esc(report.daily_report()) + "</pre>" + FOOT


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=PORT, debug=False)
