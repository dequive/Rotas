/**
 * Generates icon-192.png and icon-512.png for ROTAS Motorista PWA
 * Pure Node.js, no external dependencies.
 * Letter R on #102033 (dark navy) background.
 *
 * Usage: node scripts/generate-icons.mjs
 */
import { createWriteStream, mkdirSync } from 'fs';
import { createDeflate } from 'zlib';
import { Writable } from 'stream';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const publicDir = join(__dirname, '..', 'public');

mkdirSync(publicDir, { recursive: true });

function crc32(buf) {
  const table = (() => {
    const t = new Uint32Array(256);
    for (let i = 0; i < 256; i++) {
      let c = i;
      for (let j = 0; j < 8; j++) {
        c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      }
      t[i] = c;
    }
    return t;
  })();
  let crc = 0xffffffff;
  for (let i = 0; i < buf.length; i++) {
    crc = table[(crc ^ buf[i]) & 0xff] ^ (crc >>> 8);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function makeChunk(type, data) {
  const typeBytes = Buffer.from(type, 'ascii');
  const lenBuf = Buffer.allocUnsafe(4);
  lenBuf.writeUInt32BE(data.length, 0);
  const crcInput = Buffer.concat([typeBytes, data]);
  const crcBuf = Buffer.allocUnsafe(4);
  crcBuf.writeUInt32BE(crc32(crcInput), 0);
  return Buffer.concat([lenBuf, typeBytes, data, crcBuf]);
}

async function deflateSync(data) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    const deflate = createDeflate({ level: 9 });
    deflate.on('data', (chunk) => chunks.push(chunk));
    deflate.on('end', () => resolve(Buffer.concat(chunks)));
    deflate.on('error', reject);
    deflate.write(data);
    deflate.end();
  });
}

/**
 * Renders a single letter 'R' using a simple bitmap font pattern.
 * Draws the letter by painting pixels at known positions.
 */
function renderLetter(pixels, width, height, fg) {
  // Draw the letter R centered — using a large pixel-art approach
  // We'll use ~40% of the image height for the letter
  const letterH = Math.floor(height * 0.6);
  const letterW = Math.floor(letterH * 0.55);
  const startX = Math.floor((width - letterW) / 2);
  const startY = Math.floor((height - letterH) / 2);

  // Stroke width relative to letter size
  const sw = Math.max(2, Math.floor(letterW * 0.18));

  // Draw vertical left stroke (|)
  for (let y = startY; y < startY + letterH; y++) {
    for (let x = startX; x < startX + sw; x++) {
      setPixel(pixels, width, x, y, fg);
    }
  }

  // Draw top horizontal bar
  const armH = Math.floor(letterH * 0.5);
  for (let y = startY; y < startY + sw; y++) {
    for (let x = startX; x < startX + letterW; x++) {
      setPixel(pixels, width, x, y, fg);
    }
  }

  // Draw middle horizontal bar
  const midY = startY + armH - sw;
  for (let y = midY; y < midY + sw; y++) {
    for (let x = startX; x < startX + letterW; x++) {
      setPixel(pixels, width, x, y, fg);
    }
  }

  // Draw right top curve (right vertical for top half of R)
  for (let y = startY; y < startY + armH; y++) {
    for (let x = startX + letterW - sw; x < startX + letterW; x++) {
      setPixel(pixels, width, x, y, fg);
    }
  }

  // Draw diagonal leg of R (bottom right)
  const legStartX = startX + sw;
  const legEndX = startX + letterW;
  const legStartY = midY + sw;
  const legEndY = startY + letterH;
  const legLen = legEndY - legStartY;
  const legDX = legEndX - legStartX;

  for (let i = 0; i < legLen; i++) {
    const y = legStartY + i;
    const xCenter = legStartX + Math.floor((i * legDX) / legLen);
    for (let dx = 0; dx < sw; dx++) {
      setPixel(pixels, width, xCenter + dx, y, fg);
    }
  }
}

function setPixel(pixels, width, x, y, color) {
  if (x < 0 || y < 0 || x >= width || y >= width) return;
  const idx = (y * width + x) * 3;
  pixels[idx] = color[0];
  pixels[idx + 1] = color[1];
  pixels[idx + 2] = color[2];
}

async function generatePNG(width, height, bgColor, fgColor, outputPath) {
  // Initialize pixels with background color
  const pixels = new Uint8Array(width * height * 3);
  for (let i = 0; i < pixels.length; i += 3) {
    pixels[i] = bgColor[0];
    pixels[i + 1] = bgColor[1];
    pixels[i + 2] = bgColor[2];
  }

  // Render the letter R
  renderLetter(pixels, width, height, fgColor);

  // Build raw image data (filter byte per row)
  const rawData = Buffer.allocUnsafe(height * (1 + width * 3));
  for (let y = 0; y < height; y++) {
    rawData[y * (1 + width * 3)] = 0; // filter type None
    for (let x = 0; x < width; x++) {
      const srcIdx = (y * width + x) * 3;
      const dstIdx = y * (1 + width * 3) + 1 + x * 3;
      rawData[dstIdx] = pixels[srcIdx];
      rawData[dstIdx + 1] = pixels[srcIdx + 1];
      rawData[dstIdx + 2] = pixels[srcIdx + 2];
    }
  }

  const compressed = await deflateSync(rawData);

  // PNG signature
  const signature = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);

  // IHDR
  const ihdrData = Buffer.allocUnsafe(13);
  ihdrData.writeUInt32BE(width, 0);
  ihdrData.writeUInt32BE(height, 4);
  ihdrData[8] = 8; // bit depth
  ihdrData[9] = 2; // color type: RGB
  ihdrData[10] = 0; // compression method
  ihdrData[11] = 0; // filter method
  ihdrData[12] = 0; // interlace method
  const ihdr = makeChunk('IHDR', ihdrData);

  // IDAT
  const idat = makeChunk('IDAT', compressed);

  // IEND
  const iend = makeChunk('IEND', Buffer.alloc(0));

  const pngBytes = Buffer.concat([signature, ihdr, idat, iend]);

  await new Promise((resolve, reject) => {
    const ws = createWriteStream(outputPath);
    ws.on('finish', resolve);
    ws.on('error', reject);
    ws.write(pngBytes);
    ws.end();
  });

  console.log(`Generated ${outputPath} (${width}x${height}, ${pngBytes.length} bytes)`);
}

const BG = [0x10, 0x20, 0x33]; // #102033 dark navy
const FG = [0xff, 0xff, 0xff]; // white

await generatePNG(192, 192, BG, FG, join(publicDir, 'icon-192.png'));
await generatePNG(512, 512, BG, FG, join(publicDir, 'icon-512.png'));
console.log('PWA icons generated successfully.');
