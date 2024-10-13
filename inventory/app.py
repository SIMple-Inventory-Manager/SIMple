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
    "Settings": "/settings"
}
EMPTY_SYMBOLS = {"", " ", None}

VERSION = "0.2.1"

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
        "unallocated_quantity INTEGER, "
        "FOREIGN KEY(location) REFERENCES location(loc_id))"
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
        "category("
        "cat_id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "category_name TEXT UNIQUE NOT NULL) "
        )
    SET_CATEGORIES = (
        "prod_categories("
        "set_id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "prod_id INTEGER NOT NULL, "
        "cat_id INTEGER NOT NULL, "
        "FOREIGN KEY(prod_id) REFERENCES products(prod_id), "
        "FOREIGN KEY(cat_id) REFERENCES categories(cat_id)) "
        )
    SETTINGS = (
        "settings("
        "setting_id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "setting_name TEXT NOT NULL, "
        "setting_val INTEGER NOT NULL) "
        )

    with sqlite3.connect(DATABASE_NAME) as conn:
        for table_definition in [PRODUCTS, LOCATIONS, LOGISTICS, CATEGORIES, SET_CATEGORIES, SETTINGS]:
            conn.execute(f"CREATE TABLE IF NOT EXISTS {table_definition}")

app.init_db = init_database

def get_existing():
    with sqlite3.connect(DATABASE_NAME) as conn:
        existing = conn.execute("SELECT * FROM settings").fetchall()
        if len(existing) == 0:
            for name, value in [["loc_set", 0], ["cat_set", 0]]:
                conn.execute("INSERT INTO settings (setting_name, setting_val) VALUES (?, ?)", (name, value))

        # loc_set, loc_id | cat_set, cat_id
        loc_set = conn.execute("SELECT setting_val FROM settings WHERE setting_name = 'loc_set'").fetchone()[0]
        cat_set = conn.execute("SELECT setting_val FROM settings WHERE setting_name = 'cat_set'").fetchone()[0]
    return loc_set, cat_set

@app.route("/", methods=["GET"])
def summary():
    loc_filter, cat_filter = get_existing()

    return_args = {}
    with sqlite3.connect(DATABASE_NAME) as conn:
        location = conn.execute("SELECT * FROM location").fetchall()
        categories = conn.execute("SELECT * FROM category").fetchall()
        if loc_filter:
            return_args["loc_filter"] = 1
            return_args["filtered_loc_id"] = loc_filter
            return_args["filtered_loc_name"] = conn.execute("SELECT loc_name FROM location WHERE loc_id = ?", (str(loc_filter),)).fetchone()[0]
            products = conn.execute("SELECT * FROM products WHERE location = ? ORDER BY prod_name ASC", (str(loc_filter),)).fetchall()
        #Categories will likely be more difficult due to cross-table data
        #if cat_filter:
            #category_selected = 1
            #products = conn.execute("SELECT * FROM prod_categories WHERE cat_id = ? ORDER BY prod_name ASC", (cat_filter)).fetchall()
        else:
            return_args["loc_filter"] = 0
            products = conn.execute("SELECT * FROM products ORDER BY prod_name ASC").fetchall()

    return render_template(
        "index.jinja",
        link=VIEWS,
        title="Summary",
        extras=return_args,
        locations=location,
        categories=categories,
        products=products,
    )

@app.route("/product", methods=["POST", "GET"])
def product():
    with sqlite3.connect(DATABASE_NAME) as conn:
        warehouse = conn.execute("SELECT * FROM location ORDER BY loc_name ASC").fetchall()
        category = conn.execute("SELECT * FROM category ORDER BY category_name ASC").fetchall()

    with sqlite3.connect(DATABASE_NAME) as conn:
        if request.method == "POST":
            ## product = get_data(request)
            (prod_name,
            prod_upc,
            prod_quantity,
            quick_take_qty,
            reorder_qty,
            restock_qty,
            location,
            prod_categories,
            advanced) = (
                        request.form["prod_name"],
                        request.form["prod_upc"],
                        request.form["prod_quantity"],
                        request.form["quick_take_qty"],
                        request.form["reorder_qty"],
                        request.form["restock_qty"],
                        request.form["location"],
                        request.form["categories"],
                        request.form["advanced"]
                        )
            if advanced == "True":
                (vendor,
                 vendor_url,
                 purchase_cost,
                 sale_price) = (
                     request.form["vendor"],
                     request.form["vendor_url"],
                     request.form["purchase_cost"],
                     request.form["sale_price"]
                     )
            else:
                (vendor,
                 vendor_url,
                 purchase_cost,
                 sale_price,) = (
                     "",
                     "",
                     "",
                     "")
            ## Verify Data
            transaction_allowed = True
            for name,  value in [("Name", prod_name), ("UPC", prod_upc), ("Quantity", quick_take_qty), ("Reorder Amount", reorder_qty)]:
                if value in EMPTY_SYMBOLS:
                    transaction_allowed = False
                    error_type = "Required Field Left Empty"
                    return render_template(
                                    'modal.jinja',
                                    link=VIEWS,
                                    error_code=error_type,
                                    transaction_message=f"Unable to set required field, {name}",
                                    previous=VIEWS["Stock"]
                                )
            prod_quantity = int(prod_quantity)
            quick_take_qty = int(quick_take_qty)
            reorder_qty = int(reorder_qty)
            if restock_qty:
                restock_qty = int(restock_qty)
            else:
                restock_qty = 0
            for name, value in [("Quantity", prod_quantity), ("Quick Take", quick_take_qty), ("Reorder Amount", reorder_qty), ("Restock Amount", restock_qty)]:
                if value < 0:
                    transaction_allowed = False
                    error_type = "Negative Values"
                    return render_template(
                                    'modal.jinja',
                                    link=VIEWS,
                                    error_code=error_type,
                                    transaction_message=f"Unable to set {name}. Value '{value}' is invalid.",
                                    previous=VIEWS["Stock"]
                                )

            if transaction_allowed:
                conn.execute(
                    "INSERT INTO products (prod_name, prod_upc, prod_quantity, quick_take_qty, reorder_qty, restock_qty, location, vendor, vendor_url, purchase_cost, sale_price) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (prod_name, prod_upc, prod_quantity, quick_take_qty, reorder_qty, restock_qty, location, vendor, vendor_url, purchase_cost, sale_price)
                )
                if prod_categories != "":
                    prod_id = conn.execute("SELECT prod_id FROM products WHERE prod_name = ?", (prod_name,)).fetchone()
                    assign_categories(prod_id, prod_categories)
                return redirect(VIEWS["Stock"])

        products = conn.execute("SELECT * FROM products ORDER BY prod_name ASC").fetchall()
    return_args = {}
    return render_template(
        "product.jinja",
        link=VIEWS,
        products=products,
        extras=return_args,
        locations=warehouse,
        categories=category,
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
        categories = conn.execute("SELECT * FROM category").fetchall()

        amt_in_loc = {}
        for loc_id, _ in warehouse_data:
            products = conn.execute("SELECT prod_id FROM products WHERE location = ?", (loc_id,)).fetchall()
            amt_in_loc[loc_id] = len(products)

    return render_template(
        "location.jinja",
        link=VIEWS,
        warehouses=warehouse_data,
        prod_amt=amt_in_loc,
        categories=categories,
        title="Locations"
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
                return redirect(VIEWS["Locations"])

            case "category":
                cat_id = request.args.get("cat_id")
                if cat_id:
                    conn.execute(
                        "DELETE FROM prod_categories WHERE cat_id = ?", (cat_id,)
                        )
                    conn.execute(
                        "DELETE FROM category WHERE cat_id = ?", (cat_id)
                        )
                return redirect(VIEWS["Settings"])
            case _:
                return redirect(VIEWS["Summary"])

@app.route("/quick-change", methods=["GET", "POST"])
def quick_change():
    def update_qty(prod_id, qty):
        conn.execute(
                "UPDATE products SET prod_quantity = ? WHERE prod_id = ?",
                (qty, prod_id),
            )

    quick_change_type = request.args.get("type")
    if quick_change_type == "form":
        quick_change_type, prod_id, qty = (
                request.form["txn_type"],
                request.form["product_id"],
                request.form["custom_qty"]
            )
    elif quick_change_type == "upc_search":
        upc = request.form["quick-take-bar"]
        if not upc:
            return redirect(VIEWS["Summary"])
        with sqlite3.connect(DATABASE_NAME) as conn:
            prod_id = conn.execute("SELECT prod_id FROM products WHERE prod_upc = ?", (upc, )).fetchone()[0]
            if prod_id:
                qty = conn.execute("SELECT quick_take_qty FROM products WHERE prod_id = ?", (prod_id,) ).fetchone()[0]
            else:
                error_type = "Item not found"
                return render_template(
                    'modal.jinja',
                    link=VIEWS,
                    error_code=error_type,
                    transaction_message=f"Unable to locate item with UPC '<b>{upc}</b>'",
                    previous=VIEWS["Summary"]
                    )
        quick_change_type = "subtract"
    else:
        prod_id, qty = (
            request.args.get("product"),
            request.args.get("qty")
        )
    if qty:
        qty = int(qty)

    with sqlite3.connect(DATABASE_NAME) as conn:
        old_prod_quantity = conn.execute(
                "SELECT prod_quantity FROM products WHERE prod_id = ?", (prod_id,)
            ).fetchone()[0]
        match quick_change_type:
            case "subtract":
                new_qty = old_prod_quantity - qty
                if new_qty < 0:
                    new_qty = 0
                update_qty(prod_id, new_qty)
            case "add":
                new_qty = old_prod_quantity + qty
                update_qty(prod_id, new_qty)
            case "reorder":
                get_state = conn.execute("SELECT been_reordered FROM products WHERE prod_id = ?", (prod_id)).fetchone()[0]
                if get_state == 1:
                    new_state = 0
                else:
                    new_state = 1
                conn.execute(
                    "UPDATE products SET been_reordered = ? WHERE prod_id = ?", (new_state, prod_id)
                    )
            case "restock":
                restock_qty = conn.execute("SELECT restock_qty FROM products WHERE prod_id = ?", (prod_id)).fetchone()[0]
                new_qty = old_prod_quantity + restock_qty
                conn.execute(
                    "UPDATE products SET been_reordered = 0, prod_quantity = ? WHERE prod_id = ?", (new_qty, prod_id)
                    )

        return redirect(VIEWS["Summary"])

@app.route("/edit", methods=["POST"])
def edit():
    def update_db(prod_id, column, value):
        print(f"{column}, {value}")
        conn.execute(
                    f"UPDATE products SET {column} = ? WHERE prod_id = ?",
                    (value, prod_id),
                    )

    edit_record_type = request.args.get("type")

    with sqlite3.connect(DATABASE_NAME) as conn:
        match edit_record_type:
            case "location":
                loc_id, loc_name = request.form["loc_id"], request.form["loc_name"]
                if loc_name:
                    conn.execute(
                        "UPDATE location SET loc_name = ? WHERE loc_id = ?", (loc_name, loc_id)
                    )
                return redirect(VIEWS["Locations"])

            case "product":
                (prod_id,
                prod_name,
                prod_upc,
                prod_quantity,
                quick_take_qty,
                reorder_qty,
                restock_qty,
                location,
                category,
                advanced
                ) = (
                            ["Product ID", "prod_id", request.form["prod_id"]],
                            ["Product Name", "prod_name", request.form["prod_name"]],
                            ["Product UPC", "prod_upc", request.form["prod_upc"]],
                            ["Product Quantity", "prod_quantity", request.form["prod_quantity"]],
                            ["Product Quick Take", "quick_take_qty", request.form["quick_take_qty"]],
                            ["Minimum Quantity", "reorder_qty", request.form["reorder_qty"]],
                            ["Restock Quantity", "restock_qty", request.form["restock_qty"]],
                            ["Location", "location", request.form["location"]],
                            ["Category", "categories", request.form["categories"]],
                            request.form["advanced"]
                            )
                if advanced == "True":
                    (vendor,
                    vendor_url,
                    purchase_cost,
                    sale_price) = (
                        ["Vendor", 'vendor', request.form["vendor"]],
                        ["Vendor URL", "vendor_url", request.form["vendor_url"]],
                        ["Cost to Buy", "purchase_cost", request.form["purchase_cost"]],
                        ["Price to Sell", "sale_price", request.form["sale_price"]]
                        )
                else:
                    (vendor,
                    vendor_url,
                    purchase_cost,
                    sale_price,) = (
                        ["Vendor", 'vendor', False],
                        ["Vendor URL", "vendor_url", False],
                        ["Cost to Buy", "purchase_cost", False],
                        ["Price to Sell", "sale_price", False]
                        )
                ## Validate Data
                for name, _, value in [prod_quantity, quick_take_qty, reorder_qty, restock_qty]:
                    if value not in EMPTY_SYMBOLS:
                        if int(value) < 0:
                            error_type = "Negative Values"
                            return render_template(
                                            'modal.jinja',
                                            link=VIEWS,
                                            error_code=error_type,
                                            transaction_message=f"Unable to change {name}. Value '{value}' is invalid.",
                                            previous=VIEWS["Stock"]
                                        )
                changes_queue = {}
                item = prod_id[2]
                if prod_name[2]:
                    _, column, value = prod_name
                    changes_queue[column] = value
                if prod_upc[2]:
                    _, column, value = prod_upc
                    changes_queue[column] = value
                if prod_quantity[2]:
                    _, column, value = prod_quantity
                    changes_queue[column] = value
                if quick_take_qty[2]:
                    _, column, value = quick_take_qty
                    changes_queue[column] = value
                if reorder_qty[2]:
                    _, column, value = reorder_qty
                    changes_queue[column] = value
                if restock_qty[2]:
                    _, column, value = restock_qty
                    changes_queue[column] = value
                if location[2]:
                    _, column, value = location
                    changes_queue[column] = value
                if category[2]:
                    _, column, value = category
                    changes_queue[column] = value
                if vendor[2]:
                    _, column, value = vendor
                    changes_queue[column] = value
                if vendor_url[2]:
                    _, column, value = vendor_url
                    changes_queue[column] = value
                if purchase_cost[2]:
                    _, column, value = purchase_cost
                    changes_queue[column] = value
                if sale_price[2]:
                    _, column, value = sale_price
                    changes_queue[column] = value

                for col, val in changes_queue.items():
                    update_db(item, col, val)

                return redirect(VIEWS["Stock"])

            case _:
                return redirect(VIEWS["Summary"])

@app.route('/set-filter', methods=["GET", "POST"])
def set_filter():
    loc_filter = request.form["location-filter"]
    cat_filter = request.form["category-filter"]

    if (loc_filter and int(loc_filter)) or int(loc_filter) == 0:
        with sqlite3.connect(DATABASE_NAME) as conn:
            conn.execute("UPDATE settings SET setting_val = ? WHERE setting_name = 'loc_set'", (loc_filter))
    if (cat_filter and int(cat_filter) or cat_filter == 0):
        with sqlite3.connect(DATABASE_NAME) as conn:
            conn.execute("UPDATE settings SET setting_val = ? WHERE setting_name = 'cat_set'", (cat_filter))

    return redirect(VIEWS["Settings"])

@app.route("/quick-filter", methods=["POST"])
def quick_filter():
    filter_type = request.args.get("type")
    return_page = request.args.get("page")

    return_args = {}

    with sqlite3.connect(DATABASE_NAME) as conn:
        match filter_type:
            case "upc_search":
                prod_filter = request.form["quick-search-bar"]
                filtered_items = conn.execute("SELECT * FROM products WHERE prod_upc = ?", (prod_filter,)).fetchall()
            case "loc_cat":
                prod_filter = request.form["location-filter"]
                cat_filter = request.form["category-filter"]
                if prod_filter != "0":
                    return_args["loc_filter"] = 1
                    return_args["filtered_loc_id"] = prod_filter
                    return_args["filtered_loc_name"] = conn.execute(
                        "SELECT loc_name FROM location WHERE loc_id = ?", (prod_filter,)
                        ).fetchone()[0]
                else:
                    return_args["loc_filter"] = 0
                if cat_filter != "0":
                    return_args["cat_filter"] = 1
                    return_args["filtered_cat_id"] = cat_filter
                    return_args["filtered_cat_name"] = conn.execute(
                        "SELECT category_name FROM category WHERE cat_id = ?", (cat_filter,)
                        ).fetchone()[0]
                else:
                    return_args["cat_filter"] = 0

                if return_args["loc_filter"] and not return_args["cat_filter"]:
                    filtered_items = conn.execute(
                        "SELECT * FROM products WHERE location = ? ORDER BY prod_name ASC", (prod_filter,)
                        ).fetchall()
                elif not return_args["loc_filter"] and return_args["cat_filter"]:
                     filtered_items = conn.execute(
                        "SELECT * FROM products WHERE categories = ? ORDER BY prod_name ASC", (cat_filter,)
                        ).fetchall()
                elif return_args["loc_filter"] and return_args["cat_filter"]:
                    filtered_items = conn.execute(
                        "SELECT * FROM products WHERE location = ? AND categories = ? ORDER BY prod_name ASC", (prod_filter, cat_filter)
                        ).fetchall()

                else:
                   match return_page:
                       case "home":
                           return redirect(VIEWS["Summary"])
                       case "product":
                           return redirect(VIEWS["Stock"])
            case _:
                return redirect(VIEWS["Summary"])


        location = conn.execute(
            "SELECT * FROM location"
            ).fetchall()
        categories = conn.execute(
            "SELECT * FROM category"
            ).fetchall()
        match return_page:
            case "home":
                return render_template(
                    "index.jinja",
                    link=VIEWS,
                    title="Summary",
                    extras=return_args,
                    amount=len(filtered_items),
                    locations=location,
                    categories=categories,
                    products=filtered_items,
                    )

            case "product":
                return render_template(
                    "product.jinja",
                    link=VIEWS,
                    title="Stock",
                    extras=return_args,
                    locations=location,
                    categories=categories,
                    products=filtered_items,
                    )
            case _:
                return redirect(VIEWS["Summary"])


@app.route("/about", methods=["GET"])
@app.route('/help', methods=["GET"])
def help_page():
    return render_template(
        "about.jinja",
        link=VIEWS,
        title="SIMple Help",
        version=VERSION
        )

@app.route("/settings", methods=["GET"])
def settings_page():
    with sqlite3.connect(DATABASE_NAME) as conn:
        categories = conn.execute("SELECT * FROM category").fetchall()
        locations = conn.execute("SELECT * FROM location").fetchall()
    return render_template(
        "settings.jinja",
        link=VIEWS,
        title="Settings",
        categories=categories,
        locations=locations
        )
@app.route("/categories", methods=["POST"])
def categories():
    with sqlite3.connect(DATABASE_NAME) as conn:
        if request.method == "POST":
            category_name = request.form["new_category"]

            if category_name not in EMPTY_SYMBOLS:
                conn.execute("INSERT INTO category (category_name) VALUES (?)", (category_name,))
                return redirect(VIEWS["Settings"])

    return redirect(VIEWS["Settings"])

with app.app_context():
    app.init_db()
