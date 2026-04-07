from flask import Flask, render_template, request, redirect, url_for, session, flash, Response
from db import mysql, init_db
from datetime import datetime, timedelta
from MySQLdb.cursors import DictCursor
import csv

app = Flask(__name__)
app.secret_key = "gymsecret"

init_db(app)

# ---------------- LOGIN ----------------
@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        cursor = mysql.connection.cursor(DictCursor)
        cursor.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
        user = cursor.fetchone()
        cursor.close()

        if user:
            session["login"] = True
            return redirect(url_for("dashboard"))
        else:
            return render_template("login.html", error="Invalid username or password")

    return render_template("login.html")


# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if "login" not in session:
        return redirect(url_for("login"))

    cursor = mysql.connection.cursor(DictCursor)

    cursor.execute("SELECT COUNT(*) AS total FROM members")
    total_members = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM members WHERE end_date < CURDATE()")
    expired_members = cursor.fetchone()["total"]

    cursor.execute("""
        SELECT id, name, end_date
        FROM members
        WHERE end_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 7 DAY)
    """)
    expiring_soon = cursor.fetchall()

    cursor.execute("""
        SELECT DATE_FORMAT(payment_date, '%b') AS month,
               SUM(amount) AS total
        FROM payments
        GROUP BY DATE_FORMAT(payment_date, '%b')
        ORDER BY MIN(payment_date)
    """)
    revenue_data = cursor.fetchall()

    months = [row["month"] for row in revenue_data]
    amounts = [float(row["total"]) for row in revenue_data]

    cursor.close()

    return render_template("dashboard.html",
                           total_members=total_members,
                           expired_members=expired_members,
                           expiring_soon=expiring_soon,
                           months=months,
                           amounts=amounts)


# ---------------- MEMBER PROFILE ----------------
@app.route("/member/<int:member_id>")
def member_profile(member_id):
    if "login" not in session:
        return redirect(url_for("login"))

    cursor = mysql.connection.cursor(DictCursor)

    cursor.execute("SELECT m.*, p.plan_name FROM members m LEFT JOIN plans p ON m.plan_id=p.id WHERE m.id=%s", (member_id,))
    member = cursor.fetchone()

    cursor.execute("""
        SELECT amount, payment_date, next_due_date, method
        FROM payments
        WHERE member_id=%s
        ORDER BY payment_date DESC
    """, (member_id,))
    payments = cursor.fetchall()

    cursor.execute("""
        SELECT date, check_in
        FROM attendance
        WHERE member_id=%s
        ORDER BY date DESC
        LIMIT 30
    """, (member_id,))
    attendance = cursor.fetchall()

    cursor.close()

    return render_template("member_profile.html",
                           member=member,
                           payments=payments,
                           attendance=attendance)


# ---------------- MEMBERS ----------------
@app.route("/members")
def members():
    cursor = mysql.connection.cursor(DictCursor)

    cursor.execute("""
        SELECT members.*, plans.plan_name
        FROM members
        LEFT JOIN plans ON members.plan_id = plans.id
    """)

    data = cursor.fetchall()
    cursor.close()

    return render_template("members.html", members=data)


# ---------------- ADD MEMBER ----------------
@app.route("/add_member", methods=["GET", "POST"])
def add_member():
    if "login" not in session:
        return redirect(url_for("login"))

    cursor = mysql.connection.cursor(DictCursor)

    cursor.execute("SELECT * FROM plans")
    plans = cursor.fetchall()

    if request.method == "POST":
        name = request.form.get("name")
        phone = request.form.get("phone")
        plan_id = request.form.get("plan_id")

        if not name or not phone or not plan_id:
            return "All fields required"

        cursor.execute("SELECT duration_days FROM plans WHERE id=%s", (plan_id,))
        result = cursor.fetchone()

        if not result:
            return "Invalid plan selected"

        duration_days = result["duration_days"]

        start_date = datetime.today().date()
        end_date = start_date + timedelta(days=duration_days)

        cursor.execute("""
            INSERT INTO members (name, phone, plan_id, start_date, end_date, status)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (name, phone, plan_id, start_date, end_date, "Active"))

        mysql.connection.commit()
        cursor.close()

        return redirect(url_for("members"))

    cursor.close()
    return render_template("add_member.html", plans=plans)


# ---------------- EDIT MEMBER ----------------
@app.route("/edit_member/<int:member_id>", methods=["GET", "POST"])
def edit_member(member_id):
    if "login" not in session:
        return redirect(url_for("login"))

    cursor = mysql.connection.cursor(DictCursor)

    if request.method == "POST":
        name = request.form.get("name")
        phone = request.form.get("phone")
        email = request.form.get("email")
        plan_id = request.form.get("plan_id")

        cursor.execute("SELECT duration_days FROM plans WHERE id=%s", (plan_id,))
        plan = cursor.fetchone()

        if plan:
            duration = plan["duration_days"]

            start_date = datetime.today().date()
            end_date = start_date + timedelta(days=duration)

            cursor.execute("""
                UPDATE members
                SET name=%s, phone=%s, email=%s, plan_id=%s, start_date=%s, end_date=%s
                WHERE id=%s
            """, (name, phone, email, plan_id, start_date, end_date, member_id))

            mysql.connection.commit()

        return redirect(url_for("members"))

    cursor.execute("SELECT * FROM members WHERE id=%s", (member_id,))
    member = cursor.fetchone()

    cursor.execute("SELECT * FROM plans")
    plans = cursor.fetchall()

    return render_template("edit_member.html", member=member, plans=plans)


# ---------------- DELETE ----------------
@app.route("/delete_member/<int:id>")
def delete_member(id):
    if "login" not in session:
        return redirect(url_for("login"))

    cursor = mysql.connection.cursor()
    cursor.execute("DELETE FROM members WHERE id=%s", (id,))
    mysql.connection.commit()
    cursor.close()

    return redirect(url_for("members"))


# ---------------- ATTENDANCE ----------------
@app.route("/attendance", methods=["GET", "POST"])
def attendance():
    cursor = mysql.connection.cursor(DictCursor)
    message = ""

    if request.method == "POST":
        member_id = request.form.get("member_id")

        if member_id:
            cursor.execute(
                "INSERT INTO attendance (member_id, date, check_in) VALUES (%s, CURDATE(), CURTIME())",
                (member_id,)
            )
            mysql.connection.commit()
            message = "Check-in successful!"

    cursor.execute("SELECT id, name FROM members")
    members = cursor.fetchall()

    cursor.execute("""
        SELECT m.name, a.check_in
        FROM attendance a
        JOIN members m ON a.member_id = m.id
        WHERE a.date = CURDATE()
    """)
    attendance = cursor.fetchall()

    return render_template("attendance.html",
                           members=members,
                           attendance=attendance,
                           message=message)


# ---------------- RENEW ----------------
@app.route("/renew/<int:member_id>", methods=["GET", "POST"])
def renew(member_id):
    if "login" not in session:
        return redirect(url_for("login"))

    cursor = mysql.connection.cursor(DictCursor)

    cursor.execute("SELECT m.*, p.plan_name FROM members m LEFT JOIN plans p ON m.plan_id=p.id WHERE m.id=%s", (member_id,))
    member = cursor.fetchone()

    cursor.execute("SELECT * FROM plans")
    plans = cursor.fetchall()

    if request.method == "POST":
        plan_id = request.form.get("plan_id")
        method = request.form.get("method")

        if not plan_id or not method:
            return "All fields required"

        cursor.execute("SELECT * FROM plans WHERE id=%s", (plan_id,))
        plan = cursor.fetchone()

        if not plan:
            return "Invalid plan"

        amount = plan["price"]
        duration = plan["duration_days"]

        cursor.execute("SELECT CURDATE() AS today")
        today = cursor.fetchone()["today"]

        cursor.execute("SELECT DATE_ADD(CURDATE(), INTERVAL %s DAY) AS next_due", (duration,))
        next_due = cursor.fetchone()["next_due"]

        cursor.execute("""
            UPDATE members SET end_date=%s, plan_id=%s WHERE id=%s
        """, (next_due, plan_id, member_id))

        cursor.execute("""
            INSERT INTO payments (member_id, amount, payment_date, next_due_date, method)
            VALUES (%s,%s,%s,%s,%s)
        """, (member_id, amount, today, next_due, method))

        mysql.connection.commit()
        cursor.close()

        return redirect(url_for("members"))

    cursor.close()
    return render_template("renew.html", member=member, plans=plans)


# ---------------- EXPORT ----------------
@app.route("/export_members")
def export_members():
    if "login" not in session:
        return redirect(url_for("login"))

    cursor = mysql.connection.cursor(DictCursor)
    cursor.execute("SELECT name, phone, email, plan_id, start_date, end_date FROM members")
    data = cursor.fetchall()
    cursor.close()

    def generate():
        yield "Name,Phone,Email,Plan,Start Date,End Date\n"
        for row in data:
            yield f'{row["name"]},{row["phone"]},{row["email"]},{row["plan_id"]},{row["start_date"]},{row["end_date"]}\n'

    return Response(generate(),
                    mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=members.csv"})


# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.pop("login", None)
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)