$(function() {
    $('<a>')
        .addClass('expand')
        .text('▼')
        .appendTo('.expandable')
        .click(function(e) {
            $(this).parent().siblings('.collapsible').slideToggle();
            currText = $(this).text();
            $(this).text((currText == '▼') ? '▲' : '▼');
        });
    $('.collapsible').hide();
});