from flask import Flask, render_template, request, redirect, session
import mysql.connector
from datetime import date, timedelta

app = Flask(__name__)
app.secret_key = "pharmacy_secret_key"

# ---------------- DATABASE CONNECTION ----------------
def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Friends",
        database="pharmacy_db"
    )

# ---------------- CART TOTAL ----------------
def calculate_total(cart):
    return sum(float(item["total"]) for item in cart)

# ---------------- HOME ----------------
@app.route("/")
def home():
    return render_template("home.html")


# ---------------- ADMIN DASHBOARD ----------------
@app.route("/admin")
def admin():
    if "role" not in session:
        return redirect("/login")
    if session["role"] != "admin":
        return redirect("/login")
    
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM medicines")
    medicines = cur.fetchall()
    db.close()

    today = date.today()
    near_expiry = today + timedelta(days=30)

    return render_template(
        "admin_dashboard.html",
        medicines=medicines,
        today=today,
        near_expiry=near_expiry
    )

# ---------------- ADD MEDICINE ----------------
@app.route("/add_medicine", methods=["GET", "POST"])
def add_medicine():
    if request.method == "POST":
        f = request.form

        prescription_required = 1 if f.get("prescription_required") else 0

        db = get_db()
        cur = db.cursor()

        cur.execute("""
            INSERT INTO medicines
            (batch_no, name, manufacturer, quantity, cost_price, price, expiry_date, prescription_required)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            f.get("batch_no"),
            f.get("name"),
            f.get("manufacturer"),
            int(f.get("quantity", 0)),
            float(f.get("cost_price", 0)),
            float(f.get("price", 0)),
            f.get("expiry_date"),
            prescription_required
        ))

        db.commit()
        db.close()
        return redirect("/admin")

    return render_template("add_medicine.html")


# ---------------- DOCTOR CONFIRMATION ----------------
@app.route("/doctor_confirmation", methods=["GET", "POST"])
def doctor_confirmation():
    if request.method == "POST":
        doctor_name = request.form.get("doctor_name")
        reg_no = request.form.get("reg_no")

        if doctor_name and reg_no:
            session["doctor_confirmed"] = True

            batch = session.pop("pending_batch")
            qty = session.pop("pending_qty")

            return redirect("/add_to_cart_auto")

    return render_template("doctor_confirmation.html")


# ---------------- PHARMACIST PANEL ----------------
@app.route("/pharmacist", methods=["GET", "POST"])
def pharmacist():
    if "role" not in session:
        return redirect("/login")
    if session["role"] != "pharmacist":
        return redirect("/login")

    med = None
    expiry_status = ""
    expiry_color = ""
    low_stock = False

    cart = session.get("cart", [])

    total_amount = 0
    discount = 0
    final_amount = 0

    for item in cart:
        total_amount += item["price"] * item["qty"]

# ✅ Discount rule
    if total_amount >= 1000:
       discount = round(total_amount * 0.10, 2)

# ✅ FINAL AMOUNT (THIS LINE IS THE KEY)
    final_amount = total_amount - discount


    if request.method == "POST":
        batch = request.form.get("batch")

        if batch:
            db = get_db()
            cur = db.cursor(dictionary=True)
            cur.execute("SELECT * FROM medicines WHERE batch_no=%s", (batch,))
            med = cur.fetchone()
            db.close()

            if med:
                today = date.today()
                near = today + timedelta(days=30)

                if med["expiry_date"] < today:
                    expiry_status = "❌ EXPIRED"
                    expiry_color = "red"
                elif med["expiry_date"] <= near:
                    expiry_status = "⚠ NEAR EXPIRY"
                    expiry_color = "orange"
                else:
                    expiry_status = "✅ SAFE"
                    expiry_color = "green"

                if med["quantity"] <= 5:
                    low_stock = True

    return render_template(
    "sell_medicine.html",
    cart=cart,
    total_amount=total_amount,
    discount=discount,
    final_amount=final_amount,
    med=med,
    expiry_status=expiry_status,
    expiry_color=expiry_color,
    low_stock=low_stock
)



# ---------------- LOW STOCK ----------------
@app.route("/low_stock")
def low_stock_page():
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM medicines WHERE quantity <= 10")
    medicines = cur.fetchall()
    db.close()
    return render_template("low_stock.html", medicines=medicines)

# ---------------- NEAR EXPIRY ----------------
@app.route("/near_expiry")
def near_expiry():
    today = date.today()
    near = today + timedelta(days=30)

    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT * FROM medicines
        WHERE expiry_date > %s AND expiry_date <= %s
        ORDER BY expiry_date
    """, (today, near))
    medicines = cur.fetchall()
    db.close()

    return render_template("near_expiry_tablet.html", medicines=medicines)

# ---------------- EXPIRED MEDICINES ----------------
@app.route("/expired_medicines")
def expired_medicines():
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM medicines WHERE expiry_date < %s", (date.today(),))
    medicines = cur.fetchall()
    db.close()
    return render_template("expired_medicines.html", medicines=medicines)

# ---------------- DELETE EXPIRED ----------------
@app.route("/delete_medicine/<batch_no>")
def delete_medicine(batch_no):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "DELETE FROM medicines WHERE batch_no=%s AND expiry_date < %s",
        (batch_no, date.today())
    )
    db.commit()
    db.close()
    return redirect("/expired_medicines")

# ---------------- ADD TO CART ----------------
@app.route("/add_to_cart", methods=["POST"])
def add_to_cart():
    batch = request.form.get("batch")
    qty = int(request.form.get("qty"))

    db = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute("""
        SELECT name, price, prescription_required
        FROM medicines WHERE batch_no=%s
    """, (batch,))
    med = cur.fetchone()

    db.close()

    if not med:
        return redirect("/pharmacist")

    # ✅ DOCTOR PRESCRIPTION CHECK
    if med["prescription_required"] == 1:
        if not session.get("doctor_confirmed"):
            session["pending_batch"] = batch
            session["pending_qty"] = qty
            return redirect("/doctor_confirmation")

    cart = session.get("cart", [])

    cart.append({
        "batch": batch,
        "name": med["name"],
        "qty": qty,
        "price": float(med["price"]),
        "total": float(med["price"]) * qty
    })

    session["cart"] = cart
    return redirect("/pharmacist")


# ---------------- AUTO ADD TO CART AFTER DOCTOR CONFIRMATION ----------------
@app.route("/add_to_cart_auto")
def add_to_cart_auto():
    batch = session.get("pending_batch")
    qty = session.get("pending_qty")

    if not batch:
        return redirect("/pharmacist")

    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT name, price FROM medicines WHERE batch_no=%s", (batch,))
    med = cur.fetchone()
    db.close()

    cart = session.get("cart", [])
    cart.append({
        "batch": batch,
        "name": med["name"],
        "qty": qty,
        "price": float(med["price"]),
        "total": float(med["price"]) * qty
    })

    session["cart"] = cart
    return redirect("/pharmacist")


# ---------------- REMOVE FROM CART ----------------
@app.route("/remove_from_cart/<int:index>")
def remove_from_cart(index):
    cart = session.get("cart", [])
    if 0 <= index < len(cart):
        cart.pop(index)
        session["cart"] = cart
    return redirect("/pharmacist")

# ---------------- CUSTOMER DETAILS ----------------
@app.route("/customer_details", methods=["GET", "POST"])
def customer_details():
    if "cart" not in session or not session["cart"]:
        return redirect("/pharmacist")

    if request.method == "POST":
        session["customer"] = {
            "name": request.form["name"],
            "phone": request.form["phone"]
        }
        return redirect("/billing")

    return render_template("customer_details.html")



    
# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute(
            "SELECT * FROM users WHERE username=%s AND password=%s",
            (username, password)
        )
        user = cur.fetchone()
        cur.close()
        db.close()

        if user:
            session.clear()
            session["user"] = user["username"]
            session["role"] = user["role"]

            if user["role"] == "admin":
                return redirect("/admin")
            elif user["role"] == "pharmacist":
                return redirect("/pharmacist")
        else:
            error = "Invalid username or password"

    return render_template("login.html", error=error)


# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        db = get_db()
        cur = db.cursor()
        try:
            cur.execute(
                "INSERT INTO users (username, password, role) VALUES (%s,%s,%s)",
                (
                    request.form["username"],
                    request.form["password"],
                    request.form["role"]
                )
            )
            db.commit()
        except:
            db.rollback()
        finally:
            cur.close()
            db.close()

        return redirect("/login")

    return render_template("register.html")


# ---------------- BILLING ----------------
@app.route("/billing")
def billing():

    cart = session.get("cart", [])
    customer = session.get("customer")

    # ❌ If customer missing, redirect back
    if not customer:
        return redirect("/customer_details")

    total_amount = 0
    for item in cart:
        total_amount += float(item["total"])

    discount = 0
    if total_amount >= 1000:
        discount = round(total_amount * 0.10, 2)

    final_amount = round(total_amount - discount, 2)

    return render_template(
        "final_bill.html",
        cart=cart,
        customer=customer,
        total_amount=total_amount,
        discount=discount,
        final_amount=final_amount
    )


# ---------------- MONTHLY REPORT ----------------
@app.route("/monthly_report")
def monthly_report():
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT
            YEAR(sale_date) AS year,
            MONTH(sale_date) AS month,
            DATE_FORMAT(MIN(sale_date),'%M %Y') AS month_name,
            SUM(total) AS total_sales,
            SUM(profit) AS total_profit
        FROM sales
        GROUP BY YEAR(sale_date), MONTH(sale_date)
        ORDER BY year DESC, month DESC
    """)
    report = cur.fetchall()
    db.close()
    return render_template("monthly_report.html", report=report)

# ---------------- SALES REPORT ----------------
@app.route("/sales_report")
def sales_report():
    db = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute("""
        SELECT
            customer_name,
            customer_phone,
            GROUP_CONCAT(medicine_name SEPARATOR ', ') AS medicines,
            SUM(quantity) AS total_quantity,
            SUM(total) AS grand_total,
            MAX(sale_date) AS sale_date
        FROM sales
        GROUP BY customer_name, customer_phone, DATE(sale_date)
        ORDER BY sale_date DESC
    """)

    sales = cur.fetchall()
    db.close()

    return render_template("sales_report.html", sales=sales)




# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
