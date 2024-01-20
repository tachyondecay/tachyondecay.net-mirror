const application_root = '';
/*
 * Reload CSRF token periodically in case page has been sitting there
 */
async function refreshCSRF() {
    const input = document.querySelectorAll('[name=csrf_token]');
    if(input) {
        const response = await fetch('/api/csrf/');
        data = await response.text();
        if(response.ok) {
            csrf_token = data;
            input.forEach(el => {
                el.value = data;
            });
            console.log('New token ' + data);
        } else {
            console.log('Could not fetch CSRF token: ' + data);
        }
    }
}

function notify(message, category='') {
    const notification = document.createElement('div');
    notification.classList = 'notification';
    if(category) {
        notification.classList.add('-' + category);
    }
    notification.innerHTML = message;

    document.body.prepend(notification);
    window.setTimeout(() => {
        notification.classList.add('slideUp');
    }, 3000);
}

function BackendInit() {
    document.querySelector('body').classList.remove('no-js');

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
            if(current.length > 0) {
                console.log('Updating revision history');
                var rev = current.data('view');
                current
                    .removeClass('js-revisions__current')
                // current.wrapInner('<a href="' + application_root + '/meta/blog/write/' + rev + '/" title="View this revision"></a>');
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
    // $('input[type=date]')
    //     .datepicker({
    //         dateFormat: 'yy-mm-dd',
    //     });

    // Add timepickers to the time inputs, courtesy jquery-timepicker
    // $('input[type=time]').timepicker({
    //     scrollDefault: 'now',
    //     step: 15,
    //     timeFormat: 'H:i'
    // });

    // Add text input classes to these inputs
    $('input[type=date], input[type=time]').addClass('textinput -blend');

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
    $('#search-posts').daterangepicker({
        'autoApply': true,
        'autoUpdateInput': false,
        'locale': {
            'format': 'YYYY/MM/DD'
        },
        'minYear': 2004,
        'maxYear': moment().year() + 1,
        'showDropdowns': true
    });
    $('#search-posts').on('apply.daterangepicker', function(ev, picker) {
        let sort = $('#sort_by').val().match('date_');
        if(sort) {
            sort = $('#sort_by').val();
        } else {
            sort = 'date_updated'
        }
        $(this).val(sort + ':[' + picker.startDate.format('YYYYMMDD') + ' to ' + picker.endDate.format('YYYYMMDD') + ']');
        $(this).focus();
    });


    /*
     * Autocomplete tag searching goodness
     */
    document.querySelectorAll('.tag-lookup').forEach(function(self) {
        // Create the autocomplete div
        self.style.display = 'none';
        const container = document.createElement('div'), 
              input = document.createElement('input'),
              suggestions = document.createElement('datalist');
        container.className = 'tag-list textinput -blend';
        input.className = 'input';
        input.contentEditable = true;
        suggestions.id = 'suggestions-' + self.id;
        input.setAttribute('list', suggestions.id);
        input.setAttribute('autocomplete', 'off');

        container.append(input, suggestions);

        // Add a visible tag element to th widget
        function appendTag(tag) {
            const s = document.createElement('span');
            s.className = 'tag';
            s.title = 'Delete tag';
            s.innerText = tag.trim();
            if(s.innerText != "") {
                container.insertBefore(s, input);
            }
        }

        // Clicking on a tag removes it from the list
        container.addEventListener('click', (e) => {
            if(e.target.classList.contains('tag')) {
                const r = new RegExp(",? ?" + e.target.innerText + ",? ?");
                self.value = self.value.replace(r, ',');
                e.target.remove();
            }
        });

        // Read the existing values in the list and create a visible tag for each
        self.value.split(',').forEach(appendTag);

        // Actual lookup/search functionality
        let timer;
        input.addEventListener('input', (e) => {
            if(input.value.length >= 3) {
                window.clearTimeout(timer);
                timer = window.setTimeout(() => {
                    fetch(self.dataset.url + "&term=" + input.value)
                        .then(response => response.json())
                        .then(data => {
                            suggestions.innerHTML = '';
                            if(data) {
                                data.forEach((tag) => {
                                    const r = new RegExp(tag.value + ",? ?");
                                    if(!self.value.match(r)) {
                                        const opt = document.createElement('option');
                                        opt.value = tag.value;
                                        suggestions.appendChild(opt);
                                    }
                                });
                                // input.autocomplete = 'off';
                                // input.autocomplete = 'on';
                                // suggestions.style.display = 'block';
                            }
                        })
                        .catch(error => {
                            console.log(error);
                        });
                    }, 1000);
            }
        });

        // Keyboard navigation goodness for choosing a tag from the autocomplete suggestions
        function chooseTag(e) {
            const v = input.value.trim();
            if(e.key == 'Enter') {
                e.preventDefault();
                if(v) {
                    appendTag(v);
                    self.value += ", " + v;
                    input.value = '';
                    input.focus();
                }
            } else if(e.key == 'Backspace' && v == '') {
                e.preventDefault();
                input.previousSibling.click();
            }
        }
        input.addEventListener('keydown', chooseTag);

        self.parentNode.insertBefore(container, self.nextSibling);
    });

    // Initialize special upload fields!
    $('.js-image-upload').each(function(i, v) {
        new MagnificentUpload(v);
    });

    // Automatically grab GR or StoryGraph Review ID from URL
    Array.from(document.getElementsByClassName('js-review-id')).forEach(elem => {
        elem.addEventListener('change', e => {
            e.target.value = e.target.value.split('/').slice(-1);
        });
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

    document.querySelectorAll('.-dismissable').forEach(el => {
        const a = document.createElement('a');
        a.className = 'dismiss';
        a.title = 'Clear notification';
        a.setAttribute('tabindex', true);
        el.addEventListener('click', e => {
            el.classList.add('slideUp');
        });
        el.appendChild(a);
    });

    /*
     * Sort form options
     */
    function newSearchOptions(param, value) {
        const qs = new URLSearchParams(location.search);
        qs.set(param, value);
        location.search = qs.toString();
    }
    const   sort_by = document.getElementById('sort_by'),
            sort_order = document.getElementById('order'),
            qs = new URLSearchParams(location.search);
    if(sort_by) {
        sort_by.addEventListener('change', function() {
            newSearchOptions(this.id, this.value);
        });
        sort_by.value = qs.get('sort_by') || sort_by.dataset.default;
    }
    if(sort_order) {
        sort_order.addEventListener('change', function() {
            newSearchOptions(this.id, (this.checked) ? "asc" : "desc");
        });
        sort_order.checked = (qs.get('order') == 'asc');
    }

    const search_posts = document.getElementById('search-posts');
    if(search_posts) {
        search_posts.addEventListener('keydown', function(e) {
            if(e.key == 'Enter') {
                newSearchOptions('q', this.value);
            }
        });
    }

    /*
     * Quick search for posts to edit or copy view link
     */
    Mustache.tags = ['<%', '%>'];
    document.querySelectorAll('.quicksearch').forEach(quicksearch => {
        let container = quicksearch.nextElementSibling;
        document.addEventListener('click', e => {
            if(!container.contains(e.target)) {
                container.classList.remove('-display');
            }
        });
        container.addEventListener('click', e => {
            if(e.target.parentNode.title == 'Copy link') {
                e.preventDefault();
                navigator.clipboard.writeText(e.target.parentNode.href);
                e.target.classList = 'i--checkmark';
                const copied = document.createElement('span');
                copied.innerText = 'Copied';
                copied.style.fontSize = '0.75em';
                copied.style.transition = 'all 300ms ease-in-out';
                e.target.parentNode.append(copied);
                window.setTimeout(() => { 
                    copied.style.opacity = 0; 
                    window.setTimeout(() => {
                        copied.style.display = 'none';
                        e.target.classList = 'i--copy';
                    }, 400);
                }, 2000);
            } else if (e.target.classList.contains('addtolist')) {
                let parent = e.target.parentNode;
                let field = e.target.closest('.form-field');
                let list = field.querySelector('ol');
                let template = document.getElementById('list-item-prototype');

                list.innerHTML += Mustache.render(template.innerHTML, {
                    cover: parent.dataset.cover,
                    editlink: parent.dataset.editLink,
                    // icon: (parent.classList.contains('-review')) ? 'book' : 'newspaper',
                    list_id: document.getElementById('write').dataset.id,
                    num: list.querySelectorAll('li').length + 1,
                    post_id: parent.dataset.postId,
                    title: e.target.innerText,
                    type: parent.dataset.postType
                });

                quicksearch.value = "";
                container.classList.remove('-display');
            }
        });

        quicksearch.addEventListener('keydown', e => {
            if(e.key == "Enter") {
                e.preventDefault();
                quicksearch.value = quicksearch.value.trim();
                if(quicksearch.value) {
                    fetch('/api/posts/search/?q=' + quicksearch.value)
                        .then(response => response.json())
                        .then(data => {
                            console.log(data);
                            container.textContent = '';
                            if(data.length > 0) {
                                data.forEach(item => {
                                    const result = Mustache.render(
                                        container.parentNode.querySelector('[type=x-tmpl-mustache]').innerHTML, 
                                        item
                                    );
                                    container.innerHTML += result;
                                });
                            } else {
                                container.textContent = 'No results found.';
                            }
                            container.classList.add('-display');
                            container.focus();
                        })
                        .catch(error => {
                            console.log(error);
                        });
                }
            }
        });
    })


    const tag_manager = document.querySelector('.tag-display');
    if(tag_manager) {
        Array.from(tag_manager.children).forEach(tag => {
            const label = tag.querySelector('.label');
            label.addEventListener('click', e => {
                label.setAttribute('contentEditable', true);
            });
            label.addEventListener('keydown', e => {
                if(e.key == 'Enter') {
                    e.preventDefault();
                    label.blur();
                }
            });
            label.addEventListener('blur', e => {
                label.removeAttribute('contentEditable');
                fetch('/api/tags/rename/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrf_token
                    },
                    body: JSON.stringify({
                        'old': label.dataset.oldlabel,
                        'new': label.innerText
                    })
                })
                .then(response => response.json())
                .then(data => {
                    label.dataset.oldlabel = label.innerText;
                    notify('Tag updated.', 'success');
                    console.log(data.message)
                })
                .catch(error => {
                    notify(error.message, 'error');
                });
            });


            const del = document.createElement('a');
            del.classList = 'delete i-before--bin';
            del.innerText = '';
            del.addEventListener('click', e => {
                fetch('/api/tags/delete/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrf_token
                    },
                    body: JSON.stringify({'tag': label.innerText})
                })
                .then(response => response.json())
                .then(data => {
                    tag.remove();
                    notify('Tag deleted.', 'removed');
                })
                .catch(error => {
                    notify(error.message, 'error');
                });
            })
            tag.append(del);
        });
    }


    /*
     * Drag and drop sort for List Items
     */
    document.querySelectorAll('.js-sortable').forEach(elem => {
        let sortable = new Sortable(elem, {
            onUpdate: function(evt) {
                // console.log(evt);
                evt.target.querySelectorAll('[name*=position]').forEach((elem, index) => {
                    elem.value = index + 1;
                });
            }
        });

        /*
         * Fade out and remove the list item when delete button clicked
         */
        elem.addEventListener('click', e => {
            if((e.target.nodeName == 'SPAN' || e.target.nodeName == 'BUTTON') 
                && e.target.parentNode.nodeName == 'BUTTON') {
                e.preventDefault();
                parent = e.target.closest('li');
                parent.style.opacity = '0';
            }
        });

        elem.addEventListener('transitionend', e => {
            if(e.target.nodeName == 'LI') {
                e.target.remove();
            }
        })
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
        'autoDownloadFontAwesome': false,
        'element': this.body[0],
        'spellChecker': true,
        'toolbar': [
            'preview',
            'side-by-side',
            'fullscreen',
            {
                name: 'copy-for-gr',
                action: function(editor) {
                    let text = editor.markdown(editor.value());
                    const replacements = [
                        ['<ol>', ''],
                        ['</ol>', '\r\n'],
                        ['<p>', ''],
                        ['</p>', '\r\n'],
                        ['<ul>', '\r\n'],
                        ['<li>', '  *'],
                        ['</li>', ''],
                        ['</ul>', ''],
                        ['<head></head><body>', ''],

                    ];
                    replacements.forEach(item => {
                        text = text.replaceAll(item[0], item[1]);
                    });

                    const handle = document.getElementById('handle').value;
                    const site_link = 'Originally posted on <a href="https://kara.reviews/' + handle + '/">Kara.Reviews</a>.';
                    text += '\n\n<a rel="license" href="https://creativecommons.org/licenses/by-nc/4.0/"><img alt="Creative Commons BY-NC License" width="88" height="31" src="http://i.creativecommons.org/l/by-nc/4.0/88x31.png" /></a>';

                    // Get anything that might be a link to another review
                    const review_links = text.matchAll(/href="(https:\/\/kara\.reviews)?\/([^/]+)\/?"/g);
                    let q = '';
                    for(const link of review_links) {
                        q += '&q=' + link[2];
                    }
                    if(q) {
                        fetch('/api/posts/goodreads-link/?' + q)
                            .then(response => response.json())
                            .then(data => {
                                if(data) {
                                    console.log(data);
                                    data.forEach(link => {
                                        console.log(link);
                                        text = text.replace(
                                            'https://kara.reviews/' + link[0],
                                            'https://www.goodreads.com/review/show/' + link[1]
                                        );
                                        text = text.replace(
                                            '/' + link[0],
                                            'https://www.goodreads.com/review/show/' + link[1]
                                        );
                                    });
                                    text = text.replace('</body>', site_link);
                                    console.log(text);
                                    navigator.clipboard.writeText(text);
                                    notify('Review copied to clipboard.', 'success');
                                }
                            })
                            .catch(error => {
                                console.log(error);
                            });
                    } else {
                        text = text.replace('</body>', site_link);
                        navigator.clipboard.writeText(text);
                        notify('Review copied to clipboard.', 'success');
                    }
                },
                className: 'fab fa-goodreads',
                title: 'Copy for Goodreads'
            },
            {
                name: 'copy-for-sg',
                action: function (editor) {
                    let handle = document.getElementById('handle').value;
                    let text = editor.markdown(editor.value());
                    text = text.replace('<head></head><body>', '').replace('</body>', '').replaceAll('<p>', '').replaceAll('</p>', '<br><br>');
                    text = text += 'Originally posted at <a href="https://kara.reviews/' + handle + '/">Kara.Reviews</a>.';
                    console.log(text);
                    let blob = new Blob([text], {type: "text/html"});
                    navigator.clipboard.write([new ClipboardItem({ ["text/html"]: blob })]).then(() => {
                        notify('Review copied to clipboard.', 'success');
                    });
                },
                icon: '<img src="/assets/images/icons/storygraph.png" width="25" style="cursor: pointer; vertical-align: bottom;">',
                title: 'Copy for StoryGraph'
            }
        ]
    });
}

// Autosave articles after a delay
PostForm.prototype.autosave = function() {
    var self = this;
    var new_content = self.editor.value();
    var title = self.form.find('.-title');
    var handle = self.form.find('[name=handle]');
    var type = self.form.attr('data-type');
    var parent_revision = self.body.attr('data-revision');

    // Only autosave if:
    //  * The article has a title
    //  * There have been changes
    if(title.val() && self.old_content != new_content) {
        $.post(self.autosaveConfig.ajaxURL, {
            'post_type': type,
            'body': new_content,
            'parent': parent_revision,
            'title': title.val(),
            'handle': handle.val()
        }).done(function(data, textStatus) {
            self.old_content = new_content;

            // If there was an autosave error, destroy it!
            self.form.find('.js-autosave-error').fadeOut().remove();

            if(self.form.attr('data-id') == '') {
                /*
                 * We created a new post draft.
                 *
                 * data.history contains a revision history section we can 
                 * append.
                 * 
                 * Then, add the revision id to the body field and bind the 
                 * restore function to the new "restore autosave" link.
                 */
                self.form.attr('data-id', data.post_id);
                $(data.history).hide().appendTo('#post-metadata').slideDown(500);
                self.body.attr('data-revision', data.revision_id);
                self.bindAutosaveRestores();

                // Update handle field if not empty
                if(!handle.val()) {
                    handle.val(data.handle);
                }
                // Change URL
                history.replaceState(null, null, location.href + data.post_id + "/");
                $('.page-title .subtitle').text('Editing ' + type);
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
                // self.body.attr('data-revision', data.revision_id);

                // Update URL if we are currently working with an autosave
                if(self.body.attr('is-autosave')) {
                    history.replaceState(null, null, location.href.replace(parent_revision, data.revision_id));
                }
                self.body.attr('data-is-autosave', 'true');
                self.bindAutosaveRestores();

                // Remove a warning about an extant autosave if we just made a new one
                $('.js-autosave-notification').fadeOut('fast');
            }
        }).fail(function(jqxhr, textStatus, error) {
            console.log(error);
            $('.js-revisions', self.form)
                .find('.notification.-error')
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
            .addClass('notification -success')
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
    self.input = self.container.find('[type=file]');
    self.image = self.container.find('.thumbnail');
    self.pasted = self.container.find('input[type=hidden]');
    self.placeholder = self.container.find('.placeholder');
    self.remove = self.container.find('.remove');

    self.css_no_img = '-none';

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
                    self.resetRemoveToggle((self.original_src));
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
                .data('old-src', self.image.attr('src'))
                .attr({ 'src': '', alt: '' })
                .addClass(self.css_no_img);
            self.placeholder.html('Paste image here');
        } else {
            if(self.image.data('old-src')) {
                self.image.attr({
                    'src': self.image.data('old-src'),
                    'alt': self.container.data('alt')
                }).removeClass(self.css_no_img);
            }
        }
    });

    // Generate preview thumbnail when image selected in file input
    self.input.change(function(e) {
        console.log(this);
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
    if($('#write').length > 0) {
        article = new PostForm('#write');
    }
});

