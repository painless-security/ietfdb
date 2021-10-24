/* Copyright The IETF Trust 2021, All Rights Reserved
 *
 * JS support for the SessionForm
 * */
(function() {
  'use strict';

  function initialize() {
    // Keep all the hidden inputs in sync with the main form
    const attendees_input = document.getElementById('id_attendees');
    attendees_input.addEventListener('change', function(event) {
      const hidden_inputs = document.querySelectorAll(
        '.session-details-form input[name$="-attendees"]'
      );
      for (let hi of hidden_inputs) {
        hi.value = event.target.value;
      }
    });
  }

  window.addEventListener('load', initialize);
})();