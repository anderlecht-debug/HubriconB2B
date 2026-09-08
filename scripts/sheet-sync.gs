/**
 * Hubricon lead sourcing -> Google Sheet.
 *
 * `hubricon source sheet` POSTs {secret, columns, rows} here and this upserts
 * on the `domain` column: a row already in the sheet is updated in place, a
 * new one is appended. Re-running the pass therefore refreshes the sheet
 * rather than duplicating it.
 *
 * Setup, once, about five minutes:
 *   1. Make a new Google Sheet. Any name; leave the first tab as "Sheet1"
 *      or set TAB below to whatever you rename it to.
 *   2. Extensions -> Apps Script. Delete the placeholder, paste this file.
 *   3. Edit SECRET below to a long random string.
 *   4. Deploy -> New deployment -> type "Web app".
 *        Execute as:      Me
 *        Who has access:  Anyone with the link
 *      Both matter. "Anyone with the link" is what lets the engine POST
 *      without an OAuth flow; the shared secret is what keeps it honest, and
 *      the deployment URL is unguessable.
 *   5. Copy the web app URL. In the repo's .env:
 *        SOURCING_SHEET_URL=https://script.google.com/macros/s/..../exec
 *        SOURCING_SHEET_SECRET=<the same string as SECRET below>
 *
 * If the engine reports "answered HTML rather than JSON", the deployment has
 * the wrong access setting - redeploy with the two values above.
 *
 * Nothing here sends anything to anybody. It writes rows to one spreadsheet.
 */

var SECRET = 'change-me-to-a-long-random-string';
var TAB = 'Sheet1';
var KEY = 'domain';

function doPost(e) {
  try {
    var body = JSON.parse(e.postData.contents);
    if (!SECRET || SECRET === 'change-me-to-a-long-random-string') {
      return json({ error: 'set SECRET in the Apps Script before using this' });
    }
    if (body.secret !== SECRET) {
      return json({ error: 'bad secret' });
    }
    return json(upsert(body.columns || [], body.rows || []));
  } catch (err) {
    return json({ error: String(err) });
  }
}

function upsert(columns, rows) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(TAB)
    || SpreadsheetApp.getActiveSpreadsheet().insertSheet(TAB);

  // Header. Written on first use, and rewritten if the engine's column list
  // has changed - the two are meant to be edited together.
  var width = columns.length;
  var header = sheet.getLastRow() > 0
    ? sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0]
    : [];
  if (header.join(' ') !== columns.join(' ')) {
    sheet.getRange(1, 1, 1, width).setValues([columns]);
    sheet.getRange(1, 1, 1, width).setFontWeight('bold');
    sheet.setFrozenRows(1);
  }

  var keyCol = columns.indexOf(KEY);
  if (keyCol < 0) return { error: 'rows carry no ' + KEY + ' column' };

  // Existing keys -> their row number, read in one call.
  var seen = {};
  var last = sheet.getLastRow();
  if (last > 1) {
    var keys = sheet.getRange(2, keyCol + 1, last - 1, 1).getValues();
    for (var i = 0; i < keys.length; i++) {
      if (keys[i][0]) seen[String(keys[i][0])] = i + 2;
    }
  }

  var appended = [];
  var updated = 0;
  for (var r = 0; r < rows.length; r++) {
    var row = rows[r];
    var line = [];
    for (var c = 0; c < width; c++) {
      var v = row[columns[c]];
      line.push(v === null || v === undefined ? '' : v);
    }
    var at = seen[String(row[KEY])];
    if (at) {
      sheet.getRange(at, 1, 1, width).setValues([line]);
      updated++;
    } else {
      appended.push(line);
    }
  }
  if (appended.length) {
    sheet.getRange(sheet.getLastRow() + 1, 1, appended.length, width).setValues(appended);
  }
  return { ok: true, updated: updated, added: appended.length, total: rows.length };
}

function json(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
