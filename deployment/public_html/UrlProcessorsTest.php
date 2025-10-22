<?php header('Content-Type: text/html; charset=UTF-8'); ?><!DOCTYPE html><html><head><title>URL Processors Test</title><style>body{font-family:monospace;} .pass{color:green;} .fail{color:red;} .summary{font-weight:bold;margin-top:20px;}</style></head><body><h1>URL Processors Test</h1><pre><?php
/**
 * Lightweight tests for URL processors (Dropbox, FromSmash, SwissTransfer)
 * Run via web browser
 */

require_once __DIR__ . '/../src/DropboxUrlProcessor.php';
require_once __DIR__ . '/../src/FromSmashUrlProcessor.php';
require_once __DIR__ . '/../src/SwissTransferUrlProcessor.php';

$tests = [];
$passes = 0;
$fails = 0;

function addTest($name, $fn) {
    global $tests;
    $tests[] = ['name' => $name, 'fn' => $fn];
}

function assertEquals($expected, $actual, $msg = '') {
    if ($expected !== $actual) {
        throw new Exception($msg !== '' ? $msg : ("assertEquals failed\nExpected: " . var_export($expected, true) . "\nActual:   " . var_export($actual, true)));
    }
}

function assertTrue($cond, $msg = '') {
    if (!$cond) {
        throw new Exception($msg !== '' ? $msg : 'assertTrue failed');
    }
}

// --- Dropbox tests ---
addTest('Dropbox: extract from HTML anchor and normalize dl=1', function () {
    $html = '<a href="https://www.dropbox.com/scl/fo/5nv1x2m2l96zirkn5gdq2/AEQPtGTBi0KOPEdl0MRfZoA?rlkey=y758ytvlx6ujkfl74bxwclrxg&amp;dl=0">https://www.dropbox.com/scl/fo/5nv1x2m2l96zirkn5gdq2/AEQPtGTBi0KOPEdl0MRfZoA?rlkey=y758ytvlx6ujkfl74bxwclrxg&amp;dl=0</a><br>';
    $urls = DropboxUrlProcessor::processAllDropboxUrls($html);
    assertTrue(count($urls) === 1, 'Expected exactly one Dropbox URL');
    $url = $urls[0];
    assertTrue(strpos($url, 'dl=1') !== false, 'Expected dl=1');
    assertTrue(strpos($url, '"') === false && strpos($url, '<') === false && strpos($url, '>') === false, 'URL must not contain HTML delimiters');
});

addTest('Dropbox: stray quote and fragments are stripped', function () {
    $html = 'https://www.dropbox.com/scl/fi/7ajqltb0jkb8640o3qy9w/MS.png?rlkey=c6z6h7cgx98obx5g953i4l4iw&raw=1"&dl=1';
    $urls = DropboxUrlProcessor::processAllDropboxUrls($html);
    assertTrue(count($urls) === 1, 'Expected one URL');
    $url = $urls[0];
    assertEquals('https://www.dropbox.com/scl/fi/7ajqltb0jkb8640o3qy9w/MS.png?rlkey=c6z6h7cgx98obx5g953i4l4iw&raw=1&dl=1', $url);
});

// --- FromSmash tests ---
addTest('FromSmash: extract from HTML anchor', function () {
    $html = '<a href="https://fromsmash.com/OPhYnnPgFM-ct">Download</a>';
    $urls = FromSmashUrlProcessor::processAllFromSmashUrls($html);
    assertEquals(1, count($urls), 'Expected exactly one FromSmash URL');
    assertEquals('https://fromsmash.com/OPhYnnPgFM-ct', $urls[0]);
});

addTest('FromSmash: avoid trailing HTML', function () {
    $html = 'https://fromsmash.com/ABCdef"</a><br>';
    $urls = FromSmashUrlProcessor::processAllFromSmashUrls($html);
    assertEquals(1, count($urls), 'Expected one FromSmash URL');
    assertEquals('https://fromsmash.com/ABCdef', $urls[0]);
});

// --- SwissTransfer tests ---
addTest('SwissTransfer: extract from HTML anchor', function () {
    $html = '<a href="https://www.swisstransfer.com/d/6bacf66b-9a4d-4df4-af3f-ccb96a444c12">Link</a>';
    $urls = SwissTransferUrlProcessor::processAllSwissTransferUrls($html);
    assertEquals(1, count($urls), 'Expected one SwissTransfer URL');
    assertEquals('https://www.swisstransfer.com/d/6bacf66b-9a4d-4df4-af3f-ccb96a444c12', $urls[0]);
});

addTest('SwissTransfer: avoid trailing HTML', function () {
    $html = 'https://www.swisstransfer.com/d/6bacf66b-9a4d-4df4-af3f-ccb96a444c12" target="_blank">';
    $urls = SwissTransferUrlProcessor::processAllSwissTransferUrls($html);
    assertEquals(1, count($urls), 'Expected one SwissTransfer URL');
    assertEquals('https://www.swisstransfer.com/d/6bacf66b-9a4d-4df4-af3f-ccb96a444c12', $urls[0]);
});

// --- Runner ---
foreach ($tests as $t) {
    try {
        $t['fn']();
        $passes++;
        echo "<span class='pass'>[PASS]</span> {$t['name']}<br>";
    } catch (Throwable $e) {
        $fails++;
        echo "<span class='fail'>[FAIL]</span> {$t['name']} - " . htmlspecialchars($e->getMessage()) . "<br>";
    }
}

$summary = sprintf("<br><div class='summary'>Summary: %d passed, %d failed</div>", $passes, $fails);
echo $summary;

?></pre></body></html>
