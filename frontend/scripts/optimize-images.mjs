import { mkdir } from "node:fs/promises";
import path from "node:path";
import sharp from "sharp";

const assets = path.resolve("src/assets");
const sourcePhotos = path.join(assets, "Photo-Corousel", "Photos");
const output = path.join(assets, "optimized");

await mkdir(output, { recursive: true });

const heroWidths = [768, 1280, 1920];
for (let index = 1; index <= 9; index += 1) {
  const input = path.join(sourcePhotos, `photo${index}.jpg`);
  for (const width of heroWidths) {
    const base = sharp(input).rotate().resize({ width });
    await Promise.all([
      base.clone().avif({ quality: 50, effort: 5 }).toFile(path.join(output, `hero-photo${index}-${width}.avif`)),
      base.clone().webp({ quality: 78, effort: 5 }).toFile(path.join(output, `hero-photo${index}-${width}.webp`)),
    ]);
  }
}

const logos = [
  ["rdc-logo", "RDC-NCR LOGO.png"],
  ["mmda-logo", "MMDA_Logo.png"],
  ["bagong-pilipinas-logo", "Bagong_Pilipinas_logo.png.webp"],
];
for (const [name, filename] of logos) {
  for (const width of [256, 512]) {
    await sharp(path.join(sourcePhotos, filename))
      .rotate()
      .resize({ width })
      .webp({ lossless: true, effort: 6 })
      .toFile(path.join(output, `${name}-${width}.webp`));
  }
}

for (const width of [768, 1408]) {
  const map = sharp(path.join(assets, "NCR MAP (2).png")).rotate().resize({ width });
  await Promise.all([
    map.clone().avif({ quality: 50, effort: 5 }).toFile(path.join(output, `ncr-map-${width}.avif`)),
    map.clone().webp({ quality: 78, effort: 5 }).toFile(path.join(output, `ncr-map-${width}.webp`)),
  ]);
}

console.log("Optimized hero, logo, and NCR map derivatives generated in src/assets/optimized.");
