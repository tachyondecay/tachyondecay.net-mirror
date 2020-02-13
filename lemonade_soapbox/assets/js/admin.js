/*
 * Reload CSRF token periodically in case page has been sitting there
 */
function refreshCSRF() {
    $.get('/api/csrf/').done(function(token) {
        csrf_token = token;
        console.log('New token ' + token);
        $('input[name=csrf_token]').val(token);
    });
}

function BackendInit() {
    $('body').removeClass('no-js');


    /*
     * AJAX configuration
     */
    $(document).ajaxSend(function(e, jqxhr, settings) {
        // Automatically CSRF token with request
        if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
            jqxhr.setRequestHeader("X-CSRFToken", csrf_token);
        }

        /*
         * If autosaving, we will update the Revision History with an in-progress
         * notification.
         */
        if(settings.url == (application_root + '/api/posts/autosave/')) {
            console.log('Sending autosave request.');
            var current = $('.js-revisions__current:not(.js-is-autosave)');
            if(current.size() > 0) {
                console.log('Updating revision history');
                var rev = current.data('view');
                current
                    .removeClass('js-revisions__current')
                current.wrapInner('<a href="' + application_root + '/meta/blog/write/' + rev + '/" title="View this revision"></a>');
                current.before('<li class="js-revisions__current"><span class="i--spinner"></span> Autosaving…</li>');
            } else {
                $('.js-revisions__current').html('Autosaving…');
            }
        }
    });


    /*
     * Date and time input buffs
     */
    
    // Add datepickers to the date inputs
    $('input[type=date]')
        .datepicker({
            dateFormat: 'yy-mm-dd',
        });

    // Add timepickers to the time inputs, courtesy jquery-timepicker
    $('input[type=time]').timepicker({
        scrollDefault: 'now',
        step: 15,
        timeFormat: 'H:i'
    });

    // Add text input classes to these inputs
    $('input[type=date], input[type=time]').addClass('o-text-input o-text-input--blend');

    // Add monthpickers
    $('.js-monthpicker').each(function(i, v) {
        $(v).MonthPicker({
            MonthFormat: 'yy-mm',
            SelectedMonth: $(v).data('selected'),
            MinMonth: '2004-09',
            StartYear: $(v).data('selected').substr(0, 4),
            MaxMonth: 0,
            OnAfterChooseMonth: function(selectedDate) {
                selectedDate = $.datepicker.formatDate('yy-mm', selectedDate);
                // window.location = window.location + '?month=' + selectedDate;
                // console.log(window.location + '?month=' + selectedDate);
                location.search = 'month=' + selectedDate;
            }
        });
    });

    // Activate daterange picker
    $('.js-daterangepicker').daterangepicker({
        'autoApply': true,
        'locale': {
            'format': 'YYYY/MM/DD'
        }
    });

    /*
     * Autocomplete tag searching goodness
     */
    $('.js-autocomplete:not(.js-tagit').each(function(i, v) {
        $(v).autocomplete({
            minLength: 3,
            source: $(v).data('src')
        });
    });
    $('.js-tag-search').each(function(i, v) {
        $(v).autocomplete({
            select: function(event, ui) {
                window.location = application_root + '/meta/search/?q=tag:' + ui.item.handle;
            }
        });
    });
    $('.js-autocomplete.js-tagit').tagit({
        autocomplete: {
            minLength: 3,
            source: application_root + '/api/tags/search/'
        },
        allowSpaces: true
    });
    $('.tagit')
        .removeClass('ui-widget ui-widget-content ui-corner-all')
        .addClass('o-text-input o-text-input--blend');

    // Initialize special upload fields!
    $('.js-image-upload').each(function(i, v) {
        new MagnificentUpload(v);
    });

    // Automatically strip GR Review ID from URL
    $('.js-gr').change(function(e) {
        const gr_id_regex = /^[a-z\./\:]+([0-9]+)$/i;
        var matches = $(this).val().match(gr_id_regex);
        if(matches) {
            $(this).val(matches[1]);
        }
    });

    $('#dates_read').on('apply.daterangepicker', function(e, picker) {
        if(!$('#date_published-date').val()) {
            $('#date_published-date').val(picker.endDate.format('YYYY-MM-DD'));
            $('#date_published-time').val('00:00:00');
        }
    });

    /*
     * Notifications
     */

    // Add a link to dismiss notifications
    $('<a title="Clear notification" class="dismiss" tabindex></a>')
        .appendTo('.-dismissable')
        .click(function(e) {
            $(this).parents('.notification').hide('scale', { origin: ["top", "center"], percent: 5, easing: "easeInOutBack" }, 750);
            e.preventDefault();
        });
}


var PostForm = function(form) {
    this.form = $(form);
    this.id = this.form.data('id');
    this.body = this.form.find('[name=body]');
    this.old_content = this.body.val(); // For autosaving

    // Initialize autosave logic
    if (this.form.data('autosave')) {
        this.autosaveConfig = {
            ajaxURL: application_root + '/api/posts/autosave/',
            delay: this.form.data('autosave') * 1000
        };
        this.autosaveTimer = setTimeout(this.autosave.bind(this), this.autosaveConfig.delay);

        // Add functionality to restore autosave to any links that are present
        this.bindAutosaveRestores();
    }


    // Initialize EasyMDE on the body
    this.editor = new EasyMDE({
        'element': this.body[0],
        'spellChecker': true,
        'toolbar': ['preview', 'side-by-side', 'fullscreen']
    });
}

// Autosave articles after a delay
PostForm.prototype.autosave = function() {
    var self = this;
    var new_content = self.editor.value();
    var title = self.form.find('.c-page-title__input');
    var handle = self.form.find('[name=handle]');
    var type = self.form.data('type');

    // Only autosave if:
    //  * The article has a title
    //  * There have been changes
    if(title.val() && self.old_content != new_content) {
        $.post(self.autosaveConfig.ajaxURL, {
            'type': type,
            'body': new_content,
            'parent': self.body.data('revision'),
            'title': title.val(),
            'handle': handle.val()
        }).done(function(data, textStatus) {
            self.old_content = new_content;

            // If there was an autosave error, destroy it!
            self.form.find('.js-autosave-error').fadeOut().remove();

            if(data.post_id) {
                /*
                 * We created a new post draft.
                 *
                 * data.history contains a revision history section we can 
                 * append.
                 * 
                 * Then, add the revision id to the body field and bind the 
                 * restore function to the new "restore autosave" link.
                 */
                self.form.data('id', data.post_id);
                $(data.history).hide().appendTo('#post-metadata').slideDown(500);
                self.body.data('revision', data.revision_id);
                self.bindAutosaveRestores();

                // Update handle field if not empty
                if(!handle.val()) {
                    handle.val(data.handle);
                }
                // Change URL
                history.replaceState(null, null, location.href + data.post_id + "/");
                $('.c-page-title__action').text('Editing ' + type + ' »');
                $('.js-view-post').attr('href', data.link);
                $('.js-date-created').prepend('<small>Created ' + data.created + '</small>');
                $('.js-reveal-on-creation').removeClass('u-hidden').show('scale');
            } else {
                /*
                 * Post already exists.
                 *
                 * Grab the revision id and date to amend the Revision History 
                 * section.
                 */
                $('.js-revisions__current', self.form)
                    .data('view', data.revision_id)
                    .addClass('js-revisions__current js-is-autosave')
                    .html('Last autosave: ' + data.date + ' <a href="#" class="c-revision__link">Restore</a>')
                    .children('a')
                        .data('content', self.old_content);
                self.bindAutosaveRestores();

                // Remove a warning about an extant autosave if we just made a new one
                $('.js-autosave-notification').fadeOut('fast');
            }
        }).fail(function(jqxhr, textStatus, error) {
            console.log(error);
            $('.js-revisions', self.form)
                .find('.c-notification--error')
                    .fadeOut('fast')
                    .remove()
                    .end()
                .append('<div class="c-notification c-notification--error js-autosave-error">Autosave failed.</div>');
        });
    } else {
        console.log('Autosave not triggered.');
    }
    self.autosaveTimer = setTimeout(self.autosave.bind(self), self.autosaveConfig.delay);
}

// Restore an existing autosave
PostForm.prototype.bindAutosaveRestores = function() {
    var self = this;
    $('.js-autosave-notification, .js-is-autosave').on('click', 'a', function(e) {
        e.preventDefault();
        self.old_content = $(this).data('content'); // Prevent another autosave triggering
        self.editor.value(self.old_content);
        $('.js-autosave-notification').fadeOut();
        var success = $('<div/>');
        success
            .addClass('c-notification c-notification--success')
            .text('Autosave restored!')
            .insertBefore(self.body)
            .fadeIn('fast')
            .delay(5000)
            .fadeOut()
            .remove();
    });
}


var MagnificentUpload = function(container) {
    var self = this;
    self.container = $(container);
    self.input = self.container.find('.o-upload__input');
    self.image = self.container.find('.o-upload__image');
    self.pasted = self.container.find('input[type=hidden]');
    self.placeholder = self.container.find('.o-upload__placeholder');
    self.remove = self.container.find('.o-upload__remove');

    self.css_no_img = 'o-upload__image--none';

    // Hide the remove toggle if no image currently uploaded
    if(self.image.hasClass(self.css_no_img)) {
        self.remove.hide();
    }
    else {
        // Let's save the original image src in case we want to restore it
        self.original_src = self.image.attr('src');
    }

    // Create a pastable area for the image uploaded
    self.image.parent()
        .pastableNonInputable()
        .on('pasteImage', function(e, data) {
            // Replace the preview image with pasted image
            // and show if necessary
            self.image.attr({
                'src': data.dataURL,
                'alt': self.container.data('alt')
            }).removeClass(self.css_no_img);

            self.pasted.val(data.dataURL);

            // Show the remove toggle, if necessary
            self.resetRemoveToggle();

            // Clear file field input
            self.input.val(null);

            // Change placeholder text
            self.placeholder
                .dblclick(function(e) {
                    if(self.original_src) {
                        self.image.attr('src', self.original_src);
                    } else {
                        self.image.addClass(self.css_no_img);
                    }
                    self.resetRemoveToggle(false);
                    $(this).text('Paste image here');

                    self.pasted.val('');
                })
                .html('Double-click to reset');
        });

    // Bind event to the remove toggle to clear image preview and file field
    this.remove.find('input[type=checkbox]').change(function(e) {
        if($(this).prop('checked')) {
            self.input.val(null);
            self.image
                .attr({ 'src': '', alt: '' })
                .addClass(self.css_no_img);
            self.placeholder.html('Paste image here');
        }
    });

    // Generate preview thumbnail when image selected in file input
    self.input.change(function(e) {
        const file = this.files[0];
        if (file.type.startsWith('image/')){
            const reader = new FileReader();
            reader.onload = (function(aImg) { return function(e) { aImg.src = e.target.result; }; })(self.image[0]);
            reader.readAsDataURL(file);

            self.image.removeClass(self.css_no_img);
            self.resetRemoveToggle();
        }
    });
}

MagnificentUpload.prototype.resetRemoveToggle = function(show = true) {
    this.remove.find('input[type=checkbox]').prop('checked', false);
    if(show) {
        this.remove.show('fast');
    } else {
        this.remove.hide('fast');
    }
}



$(function() {
    // Initialize various backend UI components
    BackendInit();

    var prevent_csrf_expiry = setInterval(refreshCSRF, 1000 * 3600);

    // Largely deals with article autosaving
    if($('#write').size() > 0) {
        article = new PostForm('#write');
    }
});

