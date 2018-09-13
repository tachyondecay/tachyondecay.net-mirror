$(function() {
    var years = $('.c-calendar-nav__item').length - 2;
    $('<li>')
        .addClass('c-calendar-nav__more')
        .append(
            $('<a>')
                .addClass('c-btn')
                .text('Show ' + years + ' more years')
                .attr('href', '#')
                .click(function(e) {
                    var self = this;
                    $(this).fadeOut('fast', function() {
                        $(self).parent().siblings().fadeIn('fast');
                    });
                    e.preventDefault();
                })
        )
        .insertAfter('.c-calendar-nav__item:eq(1)');
    $('.c-calendar-nav__item:gt(1)').hide();
});
