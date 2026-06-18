/**
 * Generates icon-192.png and icon-512.png for ROTAS Motorista PWA
 * Letter R on #102033 (dark navy) background
 * Run: node apps/driver/generate-icons.mjs
 */
import { createCanvas } from 'canvas';
import { writeFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const publicDir = join(__dirname, 'public');

function generateIcon(size, fontSize, yPos, filename) {
  const canvas = createCanvas(size, size);
  const ctx = canvas.getContext('2d');

  // Background: #102033 (dark navy)
  ctx.fillStyle = '#102033';
  ctx.fillRect(0, 0, size, size);

  // Letter R: white, centered
  ctx.fillStyle = 'white';
  ctx.font = `bold ${fontSize}px Arial, sans-serif`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'alphabetic';
  ctx.fillText('R', size / 2, yPos);

  const buffer = canvas.toBuffer('image/png');
  writeFileSync(join(publicDir, filename), buffer);
  console.log(`Generated ${filename} (${size}x${size}) — ${buffer.length} bytes`);
}

generateIcon(192, 110, 140, 'icon-192.png');
generateIcon(512, 300, 380, 'icon-512.png');
console.log('Icons generated successfully.');
