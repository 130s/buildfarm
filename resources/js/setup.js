var SORT_COLUMNS = [ 1, 2, 3, 4, 5 ];
var QUERY_TRANSFORMS = {
  'blue': 'class="o"',
  'red': 'class="m"',
  'yellow': 'class="obs"',
  'gray': 'class="i"'
};
var META_COLUMNS = 5;

window.body_ready = function() {
  var url_parts = window.location.href.split('?');
  if (url_parts[1]) {
    var query_parts = url_parts[1].split('&');
    $.each(query_parts, function(i, query_part) {
      key_val = query_part.split('=');
      switch(key_val[0]) {
        case 'q': window.queries = key_val[1]; break;
        case 's': window.sort = key_val[1]; break;
        case 'r': window.reverse = key_val[1]; break;
      }
    });
  }
};

/* Counterpart to nth-child selectors—returns the number of the child that this
 * node is. eg, how many siblings preceed it. Do note that nth-child is 1-based, 
 * while this function is zero based. */
function child_num(node) {
  return $.inArray(node, $(node).parent().children());
}

window.tbody_ready = function() {
  var table = $('table');

  // Populate the input box in the form.
  if (window.queries) {
    $('.search form input').val(window.queries.replace("+", " "));
  }

  // Hook up the event handler which fires when the input is changed.
  $('.search form input').on('input', function() {
    queries = $(this).val();
    window.filter_timeout && clearTimeout(window.filter_timeout);
    window.filter_timeout = setTimeout(function() {
      window.queries = queries;
      filter_table();
    }, 250);
  });

  // Hook up click handlers to the keyword shortcuts.
  $('.search a').on('click', function() {
    window.queries = $(this).text();
    filter_table();
    return false;
  });

  /* This mouseover handler wires up the tooltip and CI url in a JIT manner
   * when the mouse hovers on a version square. Critically important is that 
   * there's only instance of this handler: on the tbody. 
   * This is the "live" event pattern. */
  $('tbody', table).on('mouseover', 'tr td:nth-child(n+' + (META_COLUMNS + 1) + ') a', function(e) {
    var a = $(this);
    var tr = a.closest('tr');
    var repo_num = child_num(this);
    var ver = a.text();
    if (!ver) ver = $('td:nth-child(2)', tr).text();
    a.attr('title', repos[repo_num] + ': ' + ver);
    if (repo_num == 0) {
      var job_url = window.job_url_templates[child_num(a.closest('td')[0]) - META_COLUMNS];
      var pkg_name_converted = $('td div', tr).text().split(' ')[0].replace(/_/g, '-');
      a.attr('href', job_url.replace('{pkg}', pkg_name_converted));
    }
  });

  /* CSS makes the original header in the document invisible. We create a clone of that 
   * to be the "real" header, with the dimensions copied to the clone, and the clone alternatiing
   * between being position: absolute and position: fixed, depending on the scroll of the page. */ 
  var orig_header = $('thead', table);
  var header = orig_header.clone();
  header.addClass('floating').hide();
  $('table').prepend(header);
  // Insert spacer divs into the floating header to that it matches the
  // dimensions of the original table.
  $('th', header).each(function() {
    $(this).append($('<div class="spacer"></div>'));
  });
  $(window).on('resize', function() {
    // Resize the spacers to make the floating version match the original.
    $('th', header).each(function(i, el) {
      $('.spacer', this).css('width', $('tr th:nth-child(' + (i+1) + ')', orig_header).width());
    });
    header.show();
  });

  // This is an awkward race condition. The "better way" here would be to have the tfoot contain
  // dummy elements which lock the size of the table. Then the resize event could be triggered
  // immediately.
  setTimeout(function() {
    $(window).trigger('resize');
  }, 0);

  // When the page scrolls, check whether the header should be fixed or floating.
  var last_left = null;
  $(window).on('scroll', function() {
    if ($(window).scrollTop() > table.position().top) {
      // Fixed thead
      header.addClass('fixed');
      var left = window.scrollX;
      left = Math.max(left, 0);
      left = Math.min(left, table.width() - document.documentElement.clientWidth);
      if (left != last_left) {
        header.css('left', -left);
        last_left = left;
      }
    } else {
      // Floating thead
      header.removeClass('fixed');
    }
  });

  // Hook up sort logic on click to table headers.
  $('th:nth-child(-n+' + META_COLUMNS + ')', header).on('click', function() {
    var sort = child_num(this) + 1;
    if (window.sort == sort) {
      window.reverse = window.reverse ? 0 : 1;
    } else {
      window.sort = sort;
      delete window.reverse;
    }
    filter_table();
  });

  /* If there is a load-time query string which will trigger an immediate
   * filter, hide the in-progress loading of the table. Deliberately do this
   * after the header cloning dingus above, so that the header dimensions are
   * correct. */
  if (window.queries || window.sort) {
    $('tbody').css('visibility', 'hidden');
    setTimeout(function() {
      $('tbody').css('visibility', 'visible').hide();
    }, 0);
  }
};

window.body_done = function() {
  if (window.queries || window.sort) {
    filter_table();
    $('tbody').show();
  }
}

function scan_rows() {
  // TODO: Potentially could make the initial load/search more responsive by having this
  // go in chunks, with timeouts in between.
  window.rows = [];
  $('table tbody tr').each(function() {
    row_info = [$(this).html()];
    var tr = this;
    $.each(SORT_COLUMNS, function() {
      var td = $("td:nth-child(" + this + ")", tr);
      var sort_text = td.text();
      if (sort_text == '') sort_text = td.html();
      row_info.push(sort_text);
    });
    window.rows.push(row_info);
  });
  console.log("Total rows found: " + window.rows.length);
}

function filter_table() {
  // One time setup, to build up the array of row contents combined with sortable fields.
  if (!window.rows) { scan_rows(); }

  // If query provided, copy only the matching rows to the result set.
  // It not, just use the original. It gets mangled when sorting, but that's okay.
  var result_rows;
  if (window.queries) {
    var queries = window.queries.split("+");
    queries = $.map(queries, function(q) {
      // Disregard short terms.
      if (q.length < 3) return null;
      // Transform "magic" queries as necessary.
      return QUERY_TRANSFORMS[q] || q;
    });
    
    if (window.previous_queries && window.previous_queries.toString() == queries.toString() &&
        window.previous_sort == window.sort &&
        window.previous_reverse == window.reverse) {
      console.log("No change, skipping rebuilding table.");
      return
    } else {
      window.previous_queries = queries;
      window.previous_sort = window.sort;
      window.previous_reverse = window.reverse;
    }

    if (queries.length > 0) {
      console.log("Filtering for queries:", queries);
      result_rows = $.map(window.rows, function(row) {
        for (var i = 0; i < queries.length; i++) {
          if (row[0].indexOf(queries[i]) == -1) return null;
        }
        return [row];
      });
    } else {
      console.log("No query terms, returning whole set.");
      result_rows = window.rows;
    }
  } else {
    console.log("No query, returning whole set.");
    result_rows = window.rows;
  }

  console.log("Result rows found: " + result_rows.length);

  if (window.sort) {
    var sort = parseInt(window.sort);
    var order = 1;
    if (window.reverse == 1) order = -1;
    result_rows.sort(function(a, b) {
      if (a[sort] > b[sort]) return order;
      if (a[sort] < b[sort]) return -order;
      return 0;
    });
  }

  var result_rows_plain = $.map(result_rows, function(row) { return row[0]; });

  // It's still a nasty rendering pause as the browser crunches through this. A possible
  // future optimization would be to have multiple tbody elements, chunk up the resulting
  // rows, and load them in in batches, separated by zero timeouts.
  $('table tbody').html("<tr/><tr>" + result_rows_plain.join("</tr><tr>") + "</tr>");

  if (window.history && window.history.replaceState) {
    var qs = [];
    if (window.queries) qs.push("q=" + window.queries);
    if (window.sort) qs.push("s=" + window.sort);
    if (window.reverse) qs.push("r=" + window.reverse);
    var url = document.location.origin + document.location.pathname
    if (qs.length > 0) {
      url += "?" + qs.join("&");
    }
    window.history.replaceState({}, document.title, url);
  }
}

