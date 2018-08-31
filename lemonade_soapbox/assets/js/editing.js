function is_touch_device() {
    return 'ontouchstart' in window || // works on most browsers 
        'onmsgesturechange' in window; // works on ie10
}

$(function() {
    $(document).ajaxSend(function(e, jqxhr, settings) {
        if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
            jqxhr.setRequestHeader("X-CSRFToken", csrf_token)
        }

        if(settings.url == (application_root + '/api/articles/autosave/')) {
            var current = $('#history li.current:not(.autosave)');
            if(current.size() > 0) {
                var rev = current.data('view');
                current
                    .removeClass('current')
                    .wrapInner('<a href="/meta/write/' + rev + '/" title="View this revision"></a>');
                $('#history ol').prepend('<li>Autosaving…</li>');
            } else {
                $('#history li:first').text('Autosaving…');
            }
        }
    });


    /*
    Autosave article content every X seconds.
     */
    var editForm = $('#write');
    var article_id = editForm.data('article');
    var autosaveDelay = editForm.data('autosave') * 1000000;
    var autosaveTimer;
    var bodyField = $('#body');
    
    var old_content = bodyField.val();
    function autosave() {
        var new_content = bodyField.val();

        // Only autosave if there have been changes
        if(old_content != new_content && $('#title').val()) {
            $.post(application_root + '/api/articles/autosave/', {
                'body': new_content,
                'parent': bodyField.data('revision'),
                'title': $('#title').val()
            }).done(function(data, textStatus) {
                old_content = new_content;
                $('#metadata .autosave__error').fadeOut().remove();

                if(data.article_id) {
                    // We created a new article draft
                    $(data.history).hide().appendTo('#metadata').slideDown(500);
                    bodyField.data('revision', data.revision_id);
                    bindAutosaveRestores();
                    history.replaceState(null, null, location.href + data.article_id + "/");
                } else {
                    items = $('#history li');
                    items.eq(0)
                        .data('view', data.revision_id)
                        .addClass('current autosave')
                        .html('Last autosave: ' + data.date + ' <a href="#">Restore</a>')
                        .children('a')
                            .data('content', old_content);

                    // Remove a warning about an extant autosave if we just made a new one
                    $('div.autosave-restore').fadeOut('fast');
                }
            }).fail(function(jqxhr, textStatus, error) {
                var error = $('.autosave__error');
                if(error.size() == 0) {
                    $('#metadata').append('<div class="notification notification--error autosave__error">Autosave failed.</div>');
                }
            });
        }
        autosaveTimer = setTimeout(autosave, autosaveDelay);
    }
    if(autosaveDelay) {
        autosaveTimer = setTimeout(autosave, autosaveDelay);
    }

    // Restore an existing autosave
    function bindAutosaveRestores() {
        $('.autosave-restore').on('click', 'a', function(e) {
            e.preventDefault();
            old_content = $(this).data('content'); // Prevent another autosave triggering
            bodyField.val(old_content);
            $('div.autosave-restore').fadeOut();
            var success = $('<div/>');
            success
                .addClass('notification notification--success')
                .text('Autosave restored!')
                .insertBefore(bodyField.parents('.o-article-editor__fieldset'))
                .fadeIn('fast')
                .delay(5000)
                .fadeOut();
        });
    }


    /*
    Some fields will break the URL if changed
     */
    $('.published #save').click(function(e) {
        var form = $(this).parents('form');
        var handle = $('#handle');
        var pubdate = $('#date_published-date');
        var error = false;
        if(handle.val() != handle.get(0).defaultValue) {
            error = true;
            handle.parent().addClass('error');
        }
        if(pubdate.val() != pubdate.get(0).defaultValue) {
            error = true;
            pubdate.parent().addClass('error');
        }

        if(error) {
            e.preventDefault();
            $('<div/>')
                .text("This article has already been published. If you change the publication date or the URL handle, the article's URL will change.")
                .dialog({
                    buttons: [
                        {
                            text: "Ok",
                            click: function() {
                                $(this).dialog('close');
                                form.submit();
                            }
                        },
                        {
                            text: "Reset",
                            click: function() {
                                $(this).dialog('close');
                                handle.val(handle.get(0).defaultValue);
                                pubdate.val(pubdate.get(0).defaultValue);
                                form.submit();
                            }
                        }
                    ],
                    closeOnEscape: false,
                    modal: true,
                    resizable: false
                });
        }
    });


    $('input.js-autocomplete.js-tags').tagit({
        autocomplete: {
            minLength: 3,
            source: application_root + '/api/tags/search'
        },
        allowSpaces: true
    });
    $('.tagit')
        .removeClass('ui-widget ui-widget-content ui-corner-all')
        .addClass('o-text-input o-text-input--blend');

        
    $(window).resize(function() {
        hidePreview();
        scrollToggle();
    });
});