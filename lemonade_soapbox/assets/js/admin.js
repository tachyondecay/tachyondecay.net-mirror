function BackendInit() {
    $('body').removeClass('no-js');


    /*
     * AJAX configuration
     */
    $(document).ajaxSend(function(e, jqxhr, settings) {
        // Automatically CSRF token with request
        if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
            jqxhr.setRequestHeader("X-CSRFToken", csrf_token)
        }

        /*
         * If autosaving, we will update the Revision History with an in-progress
         * notification.
         */
        if(settings.url == (application_root + '/api/articles/autosave/')) {
            console.log('Sending autosave request.');
            var current = $('.js-revisions__current:not(.js-is-autosave)');
            if(current.size() > 0) {
                console.log('Updating revision history');
                var rev = current.data('view');
                current
                    .removeClass('js-revisions__current')
                current.wrapInner('<a href="' + application_root + '/meta/write/' + rev + '/" title="View this revision"></a>');
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
    if(!Modernizr.inputtypes.date) {
        $('input[type=date]')
            .datepicker({
                dateFormat: 'yy-mm-dd',
            });
    }

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

    /*
     * Autocomplete tag searching goodness
     */
    $('.js-autocomplete:not(.js-tagit').each(function(i, v) {
        $(v).autocomplete({
            minLength: 3,
            source: $(v).data('src')
        });
    });
    $('.js-autocomplete.js-tagit').tagit({
        autocomplete: {
            minLength: 3,
            source: application_root + '/api/tags/search'
        },
        allowSpaces: true
    });
    $('.tagit')
        .removeClass('ui-widget ui-widget-content ui-corner-all')
        .addClass('o-text-input o-text-input--blend')


    /*
     * Notifications
     */

    // Add a link to dismiss notifications
    $('<span title="Dismiss" class="c-notification__dismiss">❌</span>')
        .appendTo('.c-notification--dismissable')
        .click(function(e) {
            $(this).parents('.c-notification').hide('scale', { origin: ["top", "center"], percent: 25, easing: "easeInOutBack" }, 250);
        });
}


var ArticleForm = function(form) {
    this.form = $(form);
    this.id = this.form.data('article');
    this.body = this.form.find('[name=body]');
    this.old_content = this.body.val(); // For autosaving


    // Initialize autosave logic
    this.autosaveConfig = {
        ajaxURL: application_root + '/api/articles/autosave/',
        delay: this.form.data('autosave') * 1000
    };
    this.autosaveTimer = setTimeout(this.autosave.bind(this), this.autosaveConfig.delay);

    // Add functionality to restore autosave to any links that are present
    this.bindAutosaveRestores();


    // Initialize SimpleMDE on the body
    this.simplemde = new SimpleMDE({
        'element': this.body[0],
        'spellChecker': false,
        'toolbar': ['preview', 'side-by-side', 'fullscreen']
    });
}

// Autosave articles after a delay
ArticleForm.prototype.autosave = function() {
    var self = this;
    var new_content = self.simplemde.value();
    var title = $(self.form).find('[name=title]');
    var handle = $(self.form).find('[name=handle]');

    // Only autosave if:
    //  * The article has a title
    //  * There have been changes
    if(title && self.old_content != new_content) {
        $.post(self.autosaveConfig.ajaxURL, {
            'body': new_content,
            'parent': self.body.data('revision'),
            'title': title.val(),
            'handle': handle.val()
        }).done(function(data, textStatus) {
            self.old_content = new_content;

            // If there was an autosave error, destroy it!
            self.form.find('.js-autosave-error').fadeOut().remove();

            if(data.article_id) {
                /*
                 * We created a new article draft.
                 *
                 * data.history contains a revision history section we can 
                 * append.
                 * 
                 * Then, add the revision id to the body field and bind the 
                 * restore function to the new "restore autosave" link.
                 */
                self.form.data('article', data.article_id);
                $(data.history).hide().appendTo('#post-metadata').slideDown(500);
                self.body.data('revision', data.revision_id);
                self.bindAutosaveRestores();

                // Update handle field if not empty
                if(!handle.val()) {
                    handle.val(data.handle);
                }
                // Change URL
                history.replaceState(null, null, location.href + data.article_id + "/");
                $('.c-page-title__action').text('Editing Blog Post »');
                $('.js-view-post').attr('href', data.link);
                $('.js-date-created').prepend('<small>Created ' + data.created + '</small>');
                $('.js-reveal-on-creation').removeClass('u-hidden').show('scale');
            } else {
                /*
                 * Article already exists.
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

                // Remove a warning about an extant autosave if we just made a new one
                $('.js-autosave-notification').fadeOut('fast');
            }
        }).fail(function(jqxhr, textStatus, error) {
            console.log(error);
            $('.js-revisions', self.form).append('<div class="c-notification c-notification--error js-autosave-error">Autosave failed.</div>');
        });
    } else {
        console.log('Autosave not triggered.');
    }
    self.autosaveTimer = setTimeout(self.autosave.bind(self), self.autosaveConfig.delay);
}

// Restore an existing autosave
ArticleForm.prototype.bindAutosaveRestores = function() {
    var self = this;
    $('.js-autosave-notification, .js-is-autosave').on('click', 'a', function(e) {
        e.preventDefault();
        self.old_content = $(this).data('content'); // Prevent another autosave triggering
        self.simplemde.value(self.old_content);
        $('.js-autosave-notification').fadeOut();
        var success = $('<div/>');
        success
            .addClass('c-notification c-notification--success')
            .text('Autosave restored!')
            .insertBefore(self.body)
            .fadeIn('fast')
            .delay(5000)
            .fadeOut();
    });
}



$(function() {
    // Initialize various backend UI components
    BackendInit();

    // Largely deals with article autosaving
    if($('#write').size() > 0) {
        article = new ArticleForm('#write');
    }
});

