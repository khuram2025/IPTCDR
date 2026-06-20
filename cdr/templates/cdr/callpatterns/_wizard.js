(function () {
  'use strict';

  var PRESETS = [];
  var COUNTRIES = [];
  var DEFAULT_MODE = 'country';
  var BULK_CREATE_URL = '';

  try {
    var pe = document.getElementById('cp-presets-data');
    if (pe) PRESETS = JSON.parse(pe.textContent);
    var ce = document.getElementById('cp-countries-data');
    if (ce) COUNTRIES = JSON.parse(ce.textContent);
    var dm = document.getElementById('cp-default-mode');
    if (dm) DEFAULT_MODE = JSON.parse(dm.textContent) || 'country';
    var bu = document.getElementById('cp-bulk-create-url');
    if (bu) BULK_CREATE_URL = JSON.parse(bu.textContent) || '';
  } catch (e) { /* ignore */ }

  function escRe(s) {
    return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  function regexFromStored(pattern) {
    var p = (pattern || '').trim();
    if (!p) return '^$';
    if (p.charAt(0) === '^' || (p.charAt(0) === '(' && p.indexOf('|') !== -1)) return p;
    if (p === '+') return '^\\+\\d+';
    if (p === '00') return '^00\\d+';
    if (p === '^\\d{4}$' || p === '####') return '^\\d{4}$';
    return '^' + escRe(p);
  }

  function buildSmartCountryPattern(dial, minD, maxD, trunkZero) {
    var code = String(dial).replace(/\D/g, '');
    var trunk = trunkZero ? '0?' : '';
    var nat = trunk + '\\d{' + minD + ',' + maxD + '}';
    var alts = ['00' + code + nat, '\\+' + code + nat];
    if (code.length >= 3 || (code.length === 2 && code !== '1')) {
      alts.push(code + nat);
    }
    return '^(' + alts.join('|') + ')';
  }

  function getCsrfToken() {
    var inp = document.querySelector('#cpForm input[name=csrfmiddlewaretoken]');
    return inp ? inp.value : '';
  }

  var els = {};
  var debounceTimer;
  var selectedCountry = null;
  var countryChoices = null;
  var selectedIsos = [];

  function countryByIso(iso) {
    return COUNTRIES.find(function (c) { return c.iso === iso; });
  }

  function getSelectedIsos() {
    if (countryChoices) {
      return countryChoices.getValue(true);
    }
    var sel = document.getElementById('country_bulk_select');
    if (!sel) return [];
    return Array.from(sel.selectedOptions).map(function (o) { return o.value; });
  }

  function setSelectedIsos(isos) {
    if (!countryChoices) return;
    countryChoices.removeActiveItems();
    isos.forEach(function (iso) {
      countryChoices.setChoiceByValue(iso);
    });
  }

  function setMode(mode) {
    document.querySelectorAll('[data-wizard-panel]').forEach(function (el) {
      el.classList.toggle('d-none', el.getAttribute('data-wizard-panel') !== mode);
    });
    document.querySelectorAll('[data-mode-btn]').forEach(function (btn) {
      btn.classList.toggle('active', btn.getAttribute('data-mode-btn') === mode);
    });
    els.modeInput.value = mode;
    if (mode !== 'country') syncPatternFromWizard();
    else if (selectedCountry) applyCountry(selectedCountry, false);
    else syncPatternFromWizard();
  }

  function applyCountry(country, scrollTest) {
    if (!country) return;
    selectedCountry = country;
    els.modeInput.value = 'country';
    els.patternInput.value = country.pattern;
    els.callTypeSelect.value = 'international';
    if (!els.nameInput.value || els.nameInput.dataset.autofill === '1') {
      els.nameInput.value = country.rule_name || ('International - ' + country.name);
      els.nameInput.dataset.autofill = '1';
    }
    if (!els.descriptionInput.value || els.descriptionInput.dataset.autofill === '1') {
      els.descriptionInput.value = country.name;
      els.descriptionInput.dataset.autofill = '1';
    }
    if (country.rate_hint != null) els.rateInput.value = Number(country.rate_hint).toFixed(2);
    if (els.countrySelect) {
      var opt = els.countrySelect.querySelector('option[data-iso="' + country.iso + '"]');
      if (opt) els.countrySelect.value = country.iso;
    }
    els.testInput.value = (country.samples || []).join('\n');
    renderFormatPanel(country);
    updatePreview();
    if (scrollTest !== false && els.testInput) els.testInput.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function renderFormatPanel(country) {
    var panel = document.getElementById('country_formats_panel');
    var chips = document.getElementById('country_format_chips');
    var nameEl = document.getElementById('selected_country_name');
    if (!panel || !chips) return;
    if (!country) {
      panel.classList.add('d-none');
      return;
    }
    panel.classList.remove('d-none');
    if (nameEl) nameEl.textContent = country.flag + ' ' + country.name + ' (+' + country.dial + ')';
    chips.innerHTML = (country.formats || []).map(function (f) {
      return '<span class="format-chip">' + f.label + ' <code>' + f.example + '</code></span>';
    }).join('');
  }

  function bulkRateFor(country) {
    var useHints = document.getElementById('bulk_use_hints');
    var rateInput = document.getElementById('bulk_default_rate');
    if (useHints && useHints.checked) {
      return Number(country.rate_hint || 1).toFixed(2);
    }
    if (rateInput && rateInput.value !== '') {
      return Number(rateInput.value).toFixed(2);
    }
    return Number(country.rate_hint || 1).toFixed(2);
  }

  function updateBulkPanel() {
    selectedIsos = getSelectedIsos();
    var panel = document.getElementById('country_bulk_panel');
    var tbody = document.getElementById('bulk_preview_body');
    var countEl = document.getElementById('bulk_create_count');
    if (!panel) return;

    if (selectedIsos.length === 0) {
      panel.classList.add('d-none');
      renderFormatPanel(null);
      return;
    }

    if (selectedIsos.length === 1) {
      var one = countryByIso(selectedIsos[0]);
      if (one) {
        applyCountry(one, false);
        panel.classList.add('d-none');
        return;
      }
    }

    panel.classList.remove('d-none');
    renderFormatPanel(null);
    if (countEl) countEl.textContent = String(selectedIsos.length);

    if (tbody) {
      var rows = selectedIsos.map(function (iso) {
        var c = countryByIso(iso);
        if (!c) return '';
        return '<tr><td>' + c.flag + ' ' + c.name + '</td><td class="font-monospace">+' + c.dial + '</td>' +
          '<td class="text-end">' + bulkRateFor(c) + '</td></tr>';
      }).join('');
      tbody.innerHTML = rows;
    }
  }

  function onCountrySelectionChange() {
    updateBulkPanel();
  }

  function initCountryMultiSelect() {
    var select = document.getElementById('country_bulk_select');
    if (!select || typeof Choices === 'undefined') return;

    COUNTRIES.forEach(function (c) {
      var opt = document.createElement('option');
      opt.value = c.iso;
      opt.textContent = c.flag + ' ' + c.name + ' (+' + c.dial + ') — ' + Number(c.rate_hint || 1).toFixed(2) + ' SAR';
      select.appendChild(opt);
    });

    countryChoices = new Choices(select, {
      removeItemButton: true,
      searchEnabled: true,
      searchPlaceholderValue: 'Search country, ISO, or +dial…',
      placeholderValue: 'Select countries…',
      itemSelectText: '',
      shouldSort: false,
      fuseOptions: { threshold: 0.3 },
    });

    select.addEventListener('change', onCountrySelectionChange);
    select.addEventListener('addItem', onCountrySelectionChange);
    select.addEventListener('removeItem', onCountrySelectionChange);
  }

  function syncPatternFromWizard() {
    var mode = els.modeInput.value;
    var pattern = '';
    if (mode === 'prefix') {
      pattern = (els.prefixInput.value || '').trim();
    } else if (mode === 'country') {
      if (selectedCountry) {
        pattern = selectedCountry.pattern;
      } else {
        var opt = els.countrySelect && els.countrySelect.selectedOptions[0];
        if (opt && opt.dataset.iso) {
          var c = countryByIso(opt.dataset.iso);
          if (c) { applyCountry(c, false); return; }
        }
      }
    } else if (mode === 'local_ext') {
      pattern = '^\\d{4}$';
      els.callTypeSelect.value = 'local';
    } else if (mode === 'regex') {
      pattern = (els.regexInput.value || '').trim();
    }
    els.patternInput.value = pattern;
    updatePreview();
  }

  function applyPreset(preset) {
    if (!preset) return;
    selectedCountry = null;
    setSelectedIsos([]);
    setMode(preset.mode || 'prefix');
    if (preset.mode === 'prefix') els.prefixInput.value = preset.prefix || '';
    if (preset.name) { els.nameInput.value = preset.name; els.nameInput.dataset.autofill = '0'; }
    if (preset.call_type) els.callTypeSelect.value = preset.call_type;
    if (preset.rate_hint != null) els.rateInput.value = Number(preset.rate_hint).toFixed(2);
    if (preset.description) { els.descriptionInput.value = preset.description; els.descriptionInput.dataset.autofill = '0'; }
    syncPatternFromWizard();
    if (preset.samples && preset.samples.length) els.testInput.value = preset.samples.join('\n');
    runTests();
    updateBulkPanel();
  }

  function updatePreview() {
    var pattern = els.patternInput.value.trim();
    els.regexPreview.textContent = regexFromStored(pattern) || '—';
    var rate = parseFloat(els.rateInput.value) || 0;
    [1, 3, 5, 10].forEach(function (mins) {
      var tile = document.getElementById('cost_' + mins);
      if (tile) tile.textContent = (rate * mins).toFixed(2);
    });
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(runTests, 300);
  }

  function runTests() {
    var pattern = els.patternInput.value.trim();
    var numbers = (els.testInput.value || '').split(/\n/).map(function (s) { return s.trim(); }).filter(Boolean);
    if (!pattern) {
      els.testSummary.textContent = 'Select a country or enter a pattern';
      els.testResults.innerHTML = '';
      return;
    }
    var regex;
    try {
      regex = new RegExp(regexFromStored(pattern));
    } catch (e) {
      els.testSummary.textContent = 'Invalid regex: ' + e.message;
      els.testResults.innerHTML = '';
      return;
    }
    var results = numbers.map(function (n) {
      return { number: n, match: regex.test(n) };
    });
    var matched = results.filter(function (r) { return r.match; }).length;
    els.testSummary.textContent = numbers.length
      ? matched + ' of ' + numbers.length + ' numbers match'
      : 'Add sample numbers to test';
    els.testResults.innerHTML = results.map(function (r) {
      return '<div class="cp-test-row ' + (r.match ? 'match' : 'miss') + '">' +
        '<i class="ri-' + (r.match ? 'check-line' : 'close-line') + '"></i>' +
        '<span class="font-monospace">' + r.number + '</span></div>';
    }).join('');
  }

  function bulkCreateRules() {
    var isos = getSelectedIsos();
    if (!isos.length) {
      alert('Select at least one country.');
      return;
    }
    if (!BULK_CREATE_URL) return;

    var useHintsEl = document.getElementById('bulk_use_hints');
    var rateEl = document.getElementById('bulk_default_rate');
    var btn = document.getElementById('btn_bulk_create');
    var useHints = !!(useHintsEl && useHintsEl.checked);
    var payload = {
      countries: isos,
      use_rate_hints: useHints,
    };
    if (!useHints && rateEl && rateEl.value !== '') {
      payload.rate = rateEl.value;
    }

    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Creating…';
    }

    fetch(BULK_CREATE_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken(),
      },
      body: JSON.stringify(payload),
    })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
      .then(function (res) {
        if (!res.ok) {
          alert(res.data.error || 'Bulk create failed');
          return;
        }
        if (res.data.redirect) {
          window.location.href = res.data.redirect;
        }
      })
      .catch(function () { alert('Bulk create failed — check your connection.'); })
      .finally(function () {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = '<i class="ri-stack-line me-1"></i>Create <span id="bulk_create_count">' + isos.length + '</span> rules';
        }
      });
  }

  function init() {
    els.patternInput = document.getElementById('id_pattern');
    if (!els.patternInput) return;

    els.nameInput = document.getElementById('id_name');
    els.descriptionInput = document.getElementById('id_description');
    els.callTypeSelect = document.getElementById('id_call_type');
    els.rateInput = document.getElementById('id_rate_per_min');
    els.modeInput = document.getElementById('wizard_mode');
    els.prefixInput = document.getElementById('wizard_prefix');
    els.countrySelect = document.getElementById('wizard_country');
    els.regexInput = document.getElementById('wizard_regex');
    els.testInput = document.getElementById('wizard_test_numbers');
    els.regexPreview = document.getElementById('regex_preview');
    els.testResults = document.getElementById('test_results');
    els.testSummary = document.getElementById('test_summary');

    initCountryMultiSelect();

    document.querySelectorAll('[data-mode-btn]').forEach(function (btn) {
      btn.addEventListener('click', function () { setMode(btn.getAttribute('data-mode-btn')); });
    });

    document.querySelectorAll('[data-preset-id]').forEach(function (card) {
      card.addEventListener('click', function () {
        var preset = PRESETS.find(function (p) { return p.id === card.getAttribute('data-preset-id'); });
        applyPreset(preset);
        document.querySelectorAll('[data-preset-id]').forEach(function (c) { c.classList.remove('border-primary', 'shadow-sm'); });
        card.classList.add('border-primary', 'shadow-sm');
      });
    });

    var btnAll = document.getElementById('btn_country_select_all');
    if (btnAll) {
      btnAll.addEventListener('click', function () {
        setSelectedIsos(COUNTRIES.map(function (c) { return c.iso; }));
        onCountrySelectionChange();
      });
    }

    var btnClear = document.getElementById('btn_country_clear');
    if (btnClear) {
      btnClear.addEventListener('click', function () {
        setSelectedIsos([]);
        selectedCountry = null;
        onCountrySelectionChange();
      });
    }

    var btnApplyFirst = document.getElementById('btn_country_apply_first');
    if (btnApplyFirst) {
      btnApplyFirst.addEventListener('click', function () {
        var isos = getSelectedIsos();
        if (!isos.length) return;
        var c = countryByIso(isos[0]);
        if (c) {
          setMode('country');
          applyCountry(c);
        }
      });
    }

    var btnBulk = document.getElementById('btn_bulk_create');
    if (btnBulk) btnBulk.addEventListener('click', bulkCreateRules);

    var bulkRate = document.getElementById('bulk_default_rate');
    var bulkHints = document.getElementById('bulk_use_hints');
    if (bulkRate) bulkRate.addEventListener('input', updateBulkPanel);
    if (bulkHints) bulkHints.addEventListener('change', updateBulkPanel);

    if (els.countrySelect) {
      els.countrySelect.addEventListener('change', function () {
        var iso = els.countrySelect.value;
        var country = countryByIso(iso);
        if (country) {
          setSelectedIsos([iso]);
          applyCountry(country);
        }
      });
    }

    document.querySelectorAll('[data-rate-chip]').forEach(function (chip) {
      chip.addEventListener('click', function () {
        els.rateInput.value = Number(chip.getAttribute('data-rate-chip')).toFixed(2);
        updatePreview();
      });
    });

    [els.prefixInput, els.regexInput].forEach(function (el) {
      if (!el) return;
      el.addEventListener('input', syncPatternFromWizard);
    });
    els.patternInput.addEventListener('input', function () {
      selectedCountry = null;
      els.modeInput.value = 'regex';
      els.regexInput.value = els.patternInput.value;
      updatePreview();
    });
    els.rateInput.addEventListener('input', updatePreview);
    els.nameInput.addEventListener('input', function () { els.nameInput.dataset.autofill = '0'; });
    els.descriptionInput.addEventListener('input', function () { els.descriptionInput.dataset.autofill = '0'; });
    els.testInput.addEventListener('input', runTests);
    document.getElementById('btn_run_test').addEventListener('click', runTests);

    var p = els.patternInput.value.trim();
    if (p === '^\\d{4}$') {
      setMode('local_ext');
    } else if (p && (p.charAt(0) === '^' || (p.charAt(0) === '(' && p.indexOf('|') !== -1))) {
      els.regexInput.value = p;
      els.modeInput.value = 'regex';
      document.querySelectorAll('[data-wizard-panel]').forEach(function (el) {
        el.classList.toggle('d-none', el.getAttribute('data-wizard-panel') !== 'regex');
      });
      document.querySelectorAll('[data-mode-btn]').forEach(function (btn) {
        btn.classList.toggle('active', btn.getAttribute('data-mode-btn') === 'regex');
      });
      updatePreview();
    } else if (p) {
      els.prefixInput.value = p;
      setMode('prefix');
    } else {
      setMode(DEFAULT_MODE);
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
