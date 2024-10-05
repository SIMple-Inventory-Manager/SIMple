function enable_advanced(items){
    options_id = "extra-options-create";
    url_id     = "advanced-items-toggle-create";
    vendor_name = "Vendor Name";
    vendor_url = "https://examplevendor.com";
    purchase_cost = "Cost to Buy";
    sale_price = "Price to Sell"

    can_update = true;
    for (i=0; i < items.length; i++){
        if (items[i] == ""){
            can_update = false;

        }
    }
    if (items != "create"){
        options_id = "extra-options-"+items[0];
        url_id = "advanced-items-toggle-" + items[0];
    }
    if (items != "create" && can_update){
        vendor_name = items[1];
        vendor_url = items[2];
        purchase_cost = items[3];
        sale_price = items[4];
    }

    chunk = "<table>" +
            "<tr>" +
            "<td>Vendor:</td><td><input name='vendor' placeholder="+ vendor_name +" autocomplete='off'></td>" +
            "</tr><tr>" +
            "<td>Reorder from:</td><td><input name='vendor_url' placeholder="+ vendor_url +" autocomplete='off'></td>" +
            "</tr><tr>" +
            "<td>Purchase Cost:</td><td><input name='purchase_cost' placeholder="+ purchase_cost+" autocomplete='off'></td>" +
            "</tr><tr>" +
            "<td>Sale Price:</td><td><input name='sale_price' placeholder="+ sale_price +" autocomplete='off'></td>" +
            "</tr>" +
            "</table>"

        window.localStorage.setItem("previous-href", document.getElementById(url_id).href)
        window.localStorage.setItem("type", items[0])

        document.getElementById(options_id).innerHTML = chunk;
        document.getElementById(url_id).innerText = "Advanced Items ▲";
        document.getElementById(url_id).href = "javascript:disable_advanced()";
}
function disable_advanced(){
        prev_href = window.localStorage.getItem("previous-href");
        prev_id = window.localStorage.getItem("type")
        options_id = "extra-options-create";
        url_id     = "advanced-items-toggle-create";
        if (prev_id != "c"){
            options_id = "extra-options-"+ prev_id;
            url_id = "advanced-items-toggle-" + prev_id;
        }

        document.getElementById(options_id).innerHTML = "";
        document.getElementById(url_id).innerText = "Advanced Items ▼";
        document.getElementById(url_id).href = prev_href;
}

// Custom number
function clear_number(){
    document.getElementById("custom-number-box").value = "";
}
function compose_number(input){
    current_num = document.getElementById("custom-number-box").value;

    new_num = current_num + input;
    console.log("Setting new number as " + new_num);

    document.getElementById("custom-number-box").value = new_num;
}

function enable_custom(prod_id, type){
   chunk ='<input name="custom_qty" id="custom-number-box" class="custom-number-edit-box needs-space"/>'
   add = '<input name="txn_type" value="add" hidden><button class="btn btn-success" type="submit">Add</button>'
   subtract = '<input name="txn_type" value="subtract" hidden><button class="btn btn-danger" type="submit">Take</button>'

   if (type == "add"){
       chunk = chunk + add;
    }
    else if (type == "subtract"){
        chunk = chunk + subtract
    }
    document.getElementById("display-"+prod_id).innerHTML = chunk;

    keypad = generate_keypad(prod_id)
    document.getElementById("custom-insert-"+ prod_id).innerHTML = keypad;

}

function generate_keypad(prod_id){
    info = "<table><tr>"
    for (i = 1; i <= 9; i++){
        blurb = '<td><a href="javascript:compose_number('+ i +')"><button class="btn custom-number">'+ i +'</button></a></td>'
        if (i % 3 == 0 ){
            blurb += "</tr><tr>"
        }
        info += blurb
    }
    info += '</tr> <tr> <td></td>' +
    '<td><a href="javascript:compose_number(0)"><button class="btn custom-number">0</button></a></td>'+
    '<td></td></tr></table> <table><tr>' + // Close previous table so below buttons don't affect the nice grid'
    '<td><a href="javascript:clear_number()"><button class="btn custom-number-text">Clear</button></a></td>' +
    '<td><a href="javascript:disable_custom('+ prod_id +')"><button class="btn custom-number-text">Cancel</button></a></td>' +
    '</tr> </table>'
    return info
}


function disable_custom(prod_id){
    document.getElementById("display-"+prod_id).innerHTML = "";
    document.getElementById("custom-insert-"+ prod_id).innerHTML = "";
}
