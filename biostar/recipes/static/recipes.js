/*
Code that handles recipe interface goes here.
*/

function insert_run(element){

    // Get the recipe uid from the parent form.
    var form = element.closest("form");
    var uid = form.data("value");

    $.ajax("/run/interface/" + uid + "/",
       {
            type: 'GET',
            dataType: 'json',
            success: function (data) {
                if (data.status === 'success') {
                    element.html(data.html);
                    return
                }
                popup_message(form, data.msg, data.status, 2000)

            },
            error: function (xhr, status, text) {
                error_message(form, xhr, status, text)
            }
        })



}

function prepare_codemirror(element, size, mode) {

    var area = CodeMirror.fromTextArea(
        element[0],
        {
            lineNumbers: true,
            mode: mode,
        }
    );

    function update() {
        area.save();
    }

    area.on('change', update);

    area.setSize(null, size);

    return area
}

$(document).ready(function () {

    prepare_codemirror($('#code textarea'), 700, 'shell');
    prepare_codemirror($('#interface textarea'), 700, 'engine');

    //script.refresh();
    //interface.refresh();

    // Select open item or the default
    hash = window.location.hash || "#description" ;

    // Select collapsable elements
    collapse = $(".collapse");

    // Hide all collapsable elements.
    collapse.hide();

    if (hash === '#run'){
        insert_run($(hash));
        }
    // Show only the selected tab.
    $(hash).show();

    $(".clickable > .item").click(function (event) {

        // Don't trigger other behaviors.
        event.preventDefault();

        // The clicked element
        var elem = $(this);

        // Find the targeted element.
        var target_id = '#' + elem.data('value');

        // Find the current hash
        var current_id = window.location.hash;

        // The target element will have ajax inject inside of it.
        if (target_id === '#run'){
            insert_run($(target_id));

        }

        // The selected page is already active.
        if (target_id === current_id){
            return;
        }

        // Move the target so it is first, thus always opens downwards.
        $(target_id).parent().prepend($(target_id));

        // Rewrite the window  with current id.
        window.location.hash = target_id;

        // Close all open elements.
        collapse.hide("slow", function () {
            // Animation complete.
        });

        // Open the current element.
        $(target_id).show("slow", function () {
            // Animation complete.
        });

    });

});
