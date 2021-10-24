/* Copyright The IETF Trust 2021, All Rights Reserved
 *
 * JS support for the SessionForm
 * */
(function() {
  'use strict';

  function track_common_input(input, name_suffix) {
    input.addEventListener('change', function(event) {
      const hidden_inputs = document.querySelectorAll(
        '.session-details-form input[name$="-' + name_suffix + '"]'
      );
      for (let hi of hidden_inputs) {
        hi.value = event.target.value;
      }
    });
  }

  function initialize() {
    // Keep all the hidden inputs in sync with the main form
    track_common_input(document.getElementById('id_attendees'), 'attendees')
    track_common_input(document.getElementById('id_comments'), 'comments')
  }

  window.addEventListener('load', initialize);
})();