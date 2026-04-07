#!/usr/bin/env node
/**
 * PWA Icon Generator Script
 *
 * Generates all required PWA icon sizes from the source SVG.
 * Requires: sharp (npm install sharp)
 *
 * Usage: node scripts/generate-icons.js
 */

const sharp = require('sharp');
const fs = require('fs');
const path = require('path');

const ICONS_DIR = path.join(__dirname, '../public/icons');
const SOURCE_SVG = path.join(ICONS_DIR, 'icon.svg');

// All required icon sizes for PWA
const SIZES = [72, 96, 128, 144, 152, 192, 384, 512];

async function generateIcons() {
  console.log('Generating PWA icons...\n');

  // Ensure icons directory exists
  if (!fs.existsSync(ICONS_DIR)) {
    fs.mkdirSync(ICONS_DIR, { recursive: true });
  }

  // Check if source SVG exists
  if (!fs.existsSync(SOURCE_SVG)) {
    console.error(`Source SVG not found: ${SOURCE_SVG}`);
    console.log('Please create the source SVG first.');
    process.exit(1);
  }

  // Read the SVG file
  const svgBuffer = fs.readFileSync(SOURCE_SVG);

  // Generate each size
  for (const size of SIZES) {
    const outputPath = path.join(ICONS_DIR, `icon-${size}x${size}.png`);

    try {
      await sharp(svgBuffer)
        .resize(size, size, {
          fit: 'contain',
          background: { r: 14, g: 165, b: 233, alpha: 1 }, // sky-500
        })
        .png()
        .toFile(outputPath);

      console.log(`  Created: icon-${size}x${size}.png`);
    } catch (error) {
      console.error(`  Failed to create ${size}x${size}: ${error.message}`);
    }
  }

  // Generate favicon
  const faviconPath = path.join(__dirname, '../public/favicon.ico');
  try {
    await sharp(svgBuffer)
      .resize(32, 32)
      .toFile(faviconPath.replace('.ico', '.png'));
    console.log('  Created: favicon.png');
  } catch (error) {
    console.error(`  Failed to create favicon: ${error.message}`);
  }

  // Generate Apple touch icon
  const appleTouchPath = path.join(ICONS_DIR, 'apple-touch-icon.png');
  try {
    await sharp(svgBuffer)
      .resize(180, 180)
      .png()
      .toFile(appleTouchPath);
    console.log('  Created: apple-touch-icon.png');
  } catch (error) {
    console.error(`  Failed to create apple-touch-icon: ${error.message}`);
  }

  console.log('\nIcon generation complete!');
  console.log(`Icons saved to: ${ICONS_DIR}`);
}

// Run if called directly
if (require.main === module) {
  generateIcons().catch(console.error);
}

module.exports = { generateIcons };
