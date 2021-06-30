// Copyright The IETF Trust 2021, All Rights Reserved

/**
 * Agenda personalization JS methods
 *
 * Requires agenda_timezone.js and timezone.js be included.
 */
const agenda_personalize = (
  function () {
    'use strict';

    let meeting_timezone = document.getElementById('initial-data').dataset.timezone;
    let selection_inputs;
    let create_agenda_buttons;

    function generateQueryString() {
      let keywords = new Set();
      selection_inputs.forEach((inp) => {
        if (inp.checked) {
          inp.value.split(',').forEach(kw => keywords.add(kw));
        }
      });
      let result = [];
      keywords.forEach(kw => result.push(kw));
      return 'show=' + result.join(',');
    }

    function updateDisplayedUrl(query_string) {
      var base_url = window.location.href.replace(/\?.*$/, '');
      if (window.history && window.history.replaceState) {
        history.replaceState({}, document.title, base_url + '?' + query_string);
      }
    }

    function updateGeneratedUrl() {
      const query_string = generateQueryString();
      create_agenda_buttons.forEach((btn) => {
        const orig_url = btn.dataset.url;
        btn.href = orig_url + '?' + query_string;
      });
      updateDisplayedUrl(query_string);
    }

    /**
     * Update the checkbox state to match the filter parameters
     */
    function updateAgendaCheckboxes(filter_params) {
      selection_inputs.forEach((inp) => {
        const item_keywords = inp.closest('tr').dataset.filterKeywords.toLowerCase().split(',');
        if (
          agenda_filter.keyword_match(item_keywords, filter_params.show)
          && !agenda_filter.keyword_match(item_keywords, filter_params.hide)
        ) {
          inp.checked = true;
        } else {
          inp.checked = false;
        }
      });
    }

    function handleTableClick(event) {
      if (event.target.name === 'selected-sessions') {
        updateGeneratedUrl();
        const jqElt = jQuery(event.target);
        if (jqElt.tooltip) {
          jqElt.tooltip('hide');
        }
      }
    }

    window.addEventListener('load', function () {
        // Methods/variables here that are not in ietf_timezone or agenda_filter are from agenda_timezone.js

        // First, initialize_moments(). This must be done before calling any of the update methods.
        // It does not need timezone info, so safe to call before initializing ietf_timezone.
        initialize_moments();  // fills in moments in the agenda data

        // Now set up callbacks related to ietf_timezone. This must happen before calling initialize().
        // In particular, set_current_tz_cb() must be called before the update methods are called.
        set_current_tz_cb(ietf_timezone.get_current_tz);  // give agenda_timezone access to this method
        ietf_timezone.set_tz_change_callback(function (newtz) {
            update_times(newtz);
          }
        );

        // With callbacks in place, call ietf_timezone.initialize(). This will call the tz_change callback
        // after setting things up.
        ietf_timezone.initialize(meeting_timezone);

        // Now make other setup calls from agenda_timezone.js
        add_tooltips();
        init_timers();

        create_agenda_buttons = Array.from(
          document.getElementsByClassName('create-agenda-button')
        );
        selection_inputs = document.getElementsByName('selected-sessions');

        agenda_filter.set_update_callback(updateAgendaCheckboxes);
        agenda_filter.enable();

        document.getElementById('agenda-table')
        .addEventListener('click', handleTableClick);
      }
    );

    // export public interface
    return { meeting_timezone };
  }
)();