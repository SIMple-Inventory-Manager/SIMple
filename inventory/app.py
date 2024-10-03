# imports - standard imports
import json
import os
import sqlite3
from collections import defaultdict
from pathlib import Path

# imports - third party imports
from flask import Flask, redirect, render_template, request

DATABASE_NAME = "inventory.sqlite"
_DATABASE_PATH = Path(__file__).parent.parent / DATABASE_NAME
VIEWS = {
    "Summary": "/",
    "Stock": "/product",
    "Locations": "/location",
    #"Settings": "/settings"
}
EMPTY_SYMBOLS = {"", " ", None}

app = Flask(__name__)

if os.environ.get("FLASK_DEBUG") == "1":
    app.config.update(TEMPLATES_AUTO_RELOAD=True)
    DATABASE_NAME = _DATABASE_PATH.resolve()
else:
    DATABASE_NAME = os.environ.get("DATABASE_NAME") or _DATABASE_PATH.resolve()


def init_database():
    PRODUCTS = (
        "products("
        "prod_id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "prod_name TEXT UNIQUE NOT NULL, "
        "prod_upc TEXT UNIQUE NOT NULL, "
        "prod_quantity INTEGER NOT NULL, "
        "quick_take_qty INTEGER NOT NULL, "
        "reorder_qty INTEGER NOT NULL, "
        "restock_qty INTEGER, "
        "location TEXT NOT NULL, "
        "categories TEXT, "
        "been_reordered INTEGER, " # BOOL
        "vendor TEXT, "
        "vendor_url TEXT, "
        "purchase_cost INTEGER, "
        "sale_price INTEGER, "
        "unallocated_quantity INTEGER)"
    )
    LOCATIONS = "location(loc_id INTEGER PRIMARY KEY AUTOINCREMENT, loc_name TEXT UNIQUE NOT NULL)"
    LOGISTICS = (
        "logistics("
        "trans_id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "prod_id INTEGER NOT NULL, "
        "from_loc_id INTEGER NULL, "
        "to_loc_id INTEGER NULL, "
        "prod_quantity INTEGER NOT NULL, "
        "trans_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, "
        "FOREIGN KEY(prod_id) REFERENCES products(prod_id), "
        "FOREIGN KEY(from_loc_id) REFERENCES location(loc_id), "
        "FOREIGN KEY(to_loc_id) REFERENCES location(loc_id))"
    )
    CATEGORIES = (
        "categories=("
        "cat_id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "category_name TEXT UNIQUE NOT NULL) "
        )

    with sqlite3.connect(DATABASE_NAME) as conn:
        for table_definition in [PRODUCTS, LOCATIONS, LOGISTICS]:
            conn.execute(f"CREATE TABLE IF NOT EXISTS {table_definition}")


app.init_db = init_database


@app.route("/", methods=["GET"])
def summary():
    with sqlite3.connect(DATABASE_NAME) as conn:
        warehouse = conn.execute("SELECT * FROM location").fetchall()
        products = conn.execute("SELECT * FROM products ORDER BY prod_name ASC").fetchall()
        q_data = conn.execute(
            "SELECT prod_name, unallocated_quantity, prod_quantity, reorder_qty, restock_qty, been_reordered FROM products"
        ).fetchall()

    return render_template(
        "index.jinja",
        link=VIEWS,
        title="Summary",
        warehouses=warehouse,
        products=products,
        summary=q_data,
    )


@app.route("/product", methods=["POST", "GET"])
def product():
    with sqlite3.connect(DATABASE_NAME) as conn:
        warehouse = conn.execute("SELECT * FROM location").fetchall()
    

    with sqlite3.connect(DATABASE_NAME) as conn:
        if request.method == "POST":
            (prod_name,
            prod_upc,
            quantity,
            quick_take_qty, 
            reorder_qty, 
            restock_qty,
            location,
            categories) = (
                        request.form["prod_name"], 
                        request.form["prod_upc"],
                        request.form["prod_quantity"], 
                        request.form["quick_take_qty"],
                        request.form["reorder_qty"], 
                        request.form["restock_qty"],
                        request.form["location"],
                        request.form["categories"]
                        )
            ## Verify Data
            transaction_allowed = True
            try:
                quantity = int(quantity)
                quick_take_qty = int(quick_take_qty)
                restock_qty = int(restock_qty)
                reorder_qty = int(reorder_qty)
            except ValueError:
                print("Expected integer, did not recieve one.")
                transaction_allowed = False
            
            for to_check in [prod_name, prod_upc, quantity, quick_take_qty, reorder_qty, restock_qty, location]:
                if to_check in EMPTY_SYMBOLS:
                    transaction_allowed = False
            for num_validation in [quantity, quick_take_qty, reorder_qty, restock_qty]:
                if num_validation < 0:
                    transaction_allowed = False
                    return render_template(
                        'modal.jinja',
                        transaction_message=f"Please do not enter negative numbers."
                    )

            if transaction_allowed:
                conn.execute(
                    "INSERT INTO products (prod_name, prod_upc, prod_quantity, quick_take_qty, reorder_qty, restock_qty, location, categories) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (prod_name, prod_upc, quantity, quick_take_qty, reorder_qty, restock_qty, location, categories),
                )
                return redirect(VIEWS["Stock"])

        products = conn.execute("SELECT * FROM products").fetchall()

    return render_template(
        "product.jinja",
        link=VIEWS,
        products=products,
        locations=warehouse,
        title="Stock",
    )


@app.route("/location", methods=["POST", "GET"])
def location():
    with sqlite3.connect(DATABASE_NAME) as conn:
        if request.method == "POST":
            warehouse_name = request.form["warehouse_name"]

            if warehouse_name not in EMPTY_SYMBOLS:
                conn.execute("INSERT INTO location (loc_name) VALUES (?)", (warehouse_name,))
                return redirect(VIEWS["Locations"])

        warehouse_data = conn.execute("SELECT * FROM location").fetchall()

    return render_template(
        "location.jinja",
        link=VIEWS,
        warehouses=warehouse_data,
        title="Locations",
    )


def get_warehouse_data(
    conn: sqlite3.Connection, products: list[tuple], locations: list[tuple]
) -> list[tuple]:
    log_summary = []
    for p_id in [x[0] for x in products]:
        temp_prod_name = conn.execute(
            "SELECT prod_name FROM products WHERE prod_id = ?", (p_id,)
        ).fetchone()

        for l_id in [x[0] for x in locations]:
            temp_loc_name = conn.execute(
                "SELECT loc_name FROM location WHERE loc_id = ?", (l_id,)
            ).fetchone()
            sum_to_loc = conn.execute(
                "SELECT SUM(log.prod_quantity) FROM logistics log WHERE log.prod_id = ? AND log.to_loc_id = ?",
                (p_id, l_id),
            ).fetchone()
            sum_from_loc = conn.execute(
                "SELECT SUM(log.prod_quantity) FROM logistics log WHERE log.prod_id = ? AND log.from_loc_id = ?",
                (p_id, l_id),
            ).fetchone()
            log_summary += [
                temp_prod_name + temp_loc_name + ((sum_to_loc[0] or 0) - (sum_from_loc[0] or 0),)
            ]

    return log_summary


def update_warehouse_data(conn: sqlite3.Connection):
    update_unallocated_quantity = False
    prod_name, from_loc, to_loc, quantity = (
        request.form["prod_name"],
        request.form["from_loc"],
        request.form["to_loc"],
        request.form["quantity"],
    )

    # if no 'from loc' is given, that means the product is being shipped to a warehouse (init condition)
    if from_loc in EMPTY_SYMBOLS:
        column_name = "to_loc_id"
        operation = "-"
        location_name = to_loc
        update_unallocated_quantity = True

    # To Location wasn't specified, will be unallocated
    elif to_loc in EMPTY_SYMBOLS:
        column_name = "from_loc_id"
        operation = "+"
        location_name = from_loc
        update_unallocated_quantity = True

    # if 'from loc' and 'to_loc' given the product is being shipped between warehouses
    else:
        conn.execute(
            "INSERT INTO logistics (prod_id, from_loc_id, to_loc_id, prod_quantity) "
            "SELECT "
            "(SELECT prod_id FROM products WHERE prod_name = ?) as prod_id, "
            "(SELECT loc_id FROM location WHERE loc_name = ?) as from_loc_id, "
            "(SELECT loc_id FROM location WHERE loc_name = ?) as to_loc_id, "
            "(SELECT ? as prod_quantity) as prod_quantity",
            (prod_name, from_loc, to_loc, quantity),
        )

    if update_unallocated_quantity:
        conn.execute(
            f"INSERT INTO logistics (prod_id, {column_name}, prod_quantity) "
            "SELECT products.prod_id, location.loc_id, ? FROM products, location "
            "WHERE products.prod_name = ? AND location.loc_name = ?",
            (quantity, prod_name, location_name),
        )
        conn.execute(
            f"UPDATE products SET unallocated_quantity = unallocated_quantity {operation} ? WHERE prod_name = ?",
            (quantity, prod_name),
        )


def get_warehouse_map(log_summary: list):
    # summary data --> in format:
    # {'Asus Zenfone 2': {'Mahalakshmi': 50, 'Gorhe': 50},
    # 'Prada watch': {'Malad': 50, 'Mahalakshmi': 115}, 'Apple iPhone': {'Airoli': 75}}
    item_location_qty_map = defaultdict(dict)
    for row in log_summary:
        if row[1] in item_location_qty_map[row[0]]:
            item_location_qty_map[row[0]][row[1]] += row[2]
        else:
            item_location_qty_map[row[0]][row[1]] = row[2]
    return json.dumps(item_location_qty_map)


@app.route("/movement", methods=["POST", "GET"])
def movement():
    match request.method:
        case "GET":
            with sqlite3.connect(DATABASE_NAME) as conn:
                logistics_data = conn.execute("SELECT * FROM logistics").fetchall()
                products = conn.execute(
                    "SELECT prod_id, prod_name, unallocated_quantity FROM products"
                ).fetchall()
                locations = conn.execute("SELECT loc_id, loc_name FROM location").fetchall()
                warehouse_summary = get_warehouse_data(conn, products, locations)
                item_location_qty_map = get_warehouse_map(warehouse_summary)
                return render_template(
                    "movement.jinja",
                    title="Logistics",
                    link=VIEWS,
                    products=products,
                    locations=locations,
                    allocated=item_location_qty_map,
                    logistics=logistics_data,
                    summary=warehouse_summary,
                )

        case "POST":
            with sqlite3.connect(DATABASE_NAME) as conn:
                update_warehouse_data(conn)
                return redirect(VIEWS["Logistics"])


@app.route("/delete")
def delete():
    delete_record_type = request.args.get("type")

    with sqlite3.connect(DATABASE_NAME) as conn:
        match delete_record_type:
            case "product":
                product_id = request.args.get("prod_id")
                if product_id:
                    conn.execute("DELETE FROM products WHERE prod_id = ?", product_id)
                return redirect(VIEWS["Stock"])

            case "location":
                location_id = request.args.get("loc_id")
                if location_id:
                    in_place = dict(
                        conn.execute(
                            "SELECT prod_id, SUM(prod_quantity) FROM logistics WHERE to_loc_id = ? GROUP BY prod_id",
                            (location_id,),
                        ).fetchall()
                    )
                    out_place = dict(
                        conn.execute(
                            "SELECT prod_id, SUM(prod_quantity) FROM logistics WHERE from_loc_id = ? GROUP BY prod_id",
                            (location_id,),
                        ).fetchall()
                    )

                    displaced_qty = in_place.copy()
                    for x in in_place:
                        if x in out_place:
                            displaced_qty[x] = displaced_qty[x] - out_place[x]

                    for products_ in displaced_qty:
                        conn.execute(
                            "UPDATE products SET unallocated_quantity = unallocated_quantity + ? WHERE prod_id = ?",
                            (displaced_qty[products_], products_),
                        )
                    conn.execute("DELETE FROM location WHERE loc_id = ?", location_id)
                return redirect(VIEWS["Warehouses"])

            case _:
                return redirect(VIEWS["Summary"])

@app.route("/quick-change", methods=["GET", "POST"])
def quick_change():
    quick_change_type = request.args.get("type")
    if quick_change_type == "form":
        quick_change_type, prod_id, qty = (
                request.form["txn_type"],
                request.form["product_id"],
                request.form["custom_qty"]
            )
    else:
        prod_id, qty = (
            request.args.get("product"),
            request.args.get("qty")
        )
    try:
        qty = int(qty)
    except ValueError:
        return render_template(
            'modal.jinja',
            transaction_message=f"Unable to '{quick_change_type} {qty}' as '{qty}' is not a number."
        )

    with sqlite3.connect(DATABASE_NAME) as conn:
        old_prod_quantity = conn.execute(
                "SELECT prod_quantity FROM products WHERE prod_id = ?", (prod_id,)
            ).fetchone()[0]
        match quick_change_type:
            case "subtract":
                new_qty = old_prod_quantity - qty
                print(f"Will take away {qty} from {old_prod_quantity} for updated {new_qty}")
            case "add":
                new_qty = old_prod_quantity + qty
                print(f"Will add {qty} to {old_prod_quantity} for updated {new_qty}")
        if new_qty < 0:
            new_qty = 0
        conn.execute(
                "UPDATE products SET prod_quantity = ? WHERE prod_id = ?",
                (new_qty,  prod_id),
            )
        return redirect(VIEWS["Summary"])




@app.route("/edit", methods=["POST"])
def edit():
    edit_record_type = request.args.get("type")

    with sqlite3.connect(DATABASE_NAME) as conn:
        match edit_record_type:
            case "location":
                loc_id, loc_name = request.form["loc_id"], request.form["loc_name"]
                if loc_name:
                    conn.execute(
                        "UPDATE location SET loc_name = ? WHERE loc_id = ?", (loc_name, loc_id)
                    )
                return redirect(VIEWS["Warehouses"])

            case "product":
                (prod_id,
                prod_name,
                prod_upc,
                prod_quantity,
                quick_take_qty,
                reorder_qty,
                restock_qty,
                location,
                categories) = (
                            request.form["prod_id"],
                            request.form["prod_name"],
                            request.form["prod_upc"],
                            request.form["prod_quantity"],
                            request.form["quick_take_qty"],
                            request.form["reorder_qty"],
                            request.form["restock_qty"],
                            request.form["location"],
                            request.form["categories"]
                            )
                ## Validate Data
                for to_check in [prod_quantity, quick_take_qty, reorder_qty, restock_qty]:
                    if to_check not in EMPTY_SYMBOLS:
                        try:
                            if int(to_check) < 0:
                                return render_template(
                                    'modal.jinja',
                                    transaction_message=f"Please do not enter negative numbers."
                            )
                        except ValueError:
                            print("Expected integer, did not recieve one.")
                        

                if prod_name:
                    conn.execute(
                        "UPDATE products SET prod_name = ? WHERE prod_id = ?",
                        (prod_name, prod_id),
                    )
                if prod_upc:
                    conn.execute(
                        "UPDATE products SET prod_upc = ? WHERE prod_id = ?",
                        (prod_upc, prod_id)
                        )
                if prod_quantity:
                    conn.execute(
                        "UPDATE products SET prod_quantity = ? WHERE prod_id = ?",
                        (int(prod_quantity), prod_id),
                    )
                if quick_take_qty:
                    conn.execute(
                        "UPDATE products SET quick_take_qty = ? WHERE prod_id = ?",
                        (int(quick_take_qty), prod_id),
                    )
                if reorder_qty:
                    conn.execute(
                            "UPDATE products SET reorder_qty = ? WHERE prod_id = ?",
                            (int(reorder_qty), prod_id),
                    )
                if restock_qty:
                    conn.execute(
                            "UPDATE products SET restock_qty = ? WHERE prod_id = ?",
                            (int(restock_qty), prod_id),
                    )
                if location:
                    conn.execute(
                        "UPDATE products SET location = ? WHERE prod_id = ?",
                        (location, prod_id),
                    )
                if categories:
                    conn.execute(
                        "UPDATE products SET categories = ? WHERE prod_id = ?",
                        (categories, prod_id),
                    )

                return redirect(VIEWS["Stock"])

            case _:
                return redirect(VIEWS["Summary"])


with app.app_context():
    app.init_db()
