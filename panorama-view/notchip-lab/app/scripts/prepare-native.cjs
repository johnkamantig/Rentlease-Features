// Scoped compatibility fix: the published module omits android.ndkVersion,
// selecting AGP's 27.0 while SDK 57/RN selects 27.1 for the application.
// Keep the unmodified npm source in ../../package; never change C++ algorithms.
const fs = require('node:fs');
const path = require('node:path');
const pkg = require('../node_modules/@notchip/expo-panoramic-stitcher/package.json');
if (pkg.version !== '0.7.0') throw new Error('Review native preparation for new package versions');
const target = path.join(__dirname,'../node_modules/@notchip/expo-panoramic-stitcher/android/build.gradle');
const source = fs.readFileSync(target,'utf8').replaceAll('\r\n','\n');
const marker = '  ndkVersion rootProject.ext.ndkVersion // RentLease lab: match app NDK';
if (source.includes(marker)) process.exit(0);
const anchor = 'android {\n  namespace "expo.modules.panoramicstitcher"';
if (!source.includes(anchor)) throw new Error('Unexpected module Gradle file');
fs.writeFileSync(target,source.replace(anchor, 'android {\n'+marker+'\n  namespace "expo.modules.panoramicstitcher"'));
console.log('Notchip 0.7.0: aligned module NDK version with app');
