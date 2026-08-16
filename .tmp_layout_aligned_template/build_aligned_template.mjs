import fs from "node:fs/promises";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const OUTPUT = "C:\\Users\\User\\Desktop\\Combined_Predictions\\Seven_Directions_Radial_Template_Layout_Aligned.pptx";
const BUILD = "C:\\Users\\User\\Desktop\\Combined_Predictions\\.tmp_layout_aligned_template";
const REFERENCE = "C:\\Users\\User\\AppData\\Local\\Temp\\codex-clipboard-91ad45b4-9061-4202-b102-10799e39ecc1.png";

const C = {
  mint: "#66FF99",
  purple: "#7030A0",
  ink: "#2E173D",
  muted: "#746C79",
  palePurple: "#F6F0FA",
  white: "#FFFFFF",
};

async function writeBlob(path, blob) {
  await fs.writeFile(path, new Uint8Array(await blob.arrayBuffer()));
}

function addText(slide, {
  name,
  text,
  left,
  top,
  width,
  height,
  fontSize,
  color = C.ink,
  bold = false,
  alignment = "left",
  verticalAlignment = "middle",
  typeface = "Aptos Display",
  lineSpacing = 0.96,
  insets = { top: 0, right: 0, bottom: 0, left: 0 },
}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    name,
    position: { left, top, width, height },
    fill: "none",
    line: { style: "solid", fill: "none", width: 0 },
  });
  shape.text = text;
  shape.text.style = {
    fontSize,
    color,
    bold,
    alignment,
    verticalAlignment,
    typeface,
    lineSpacing,
    wrap: "none",
    autoFit: "shrinkText",
    insets,
  };
  return shape;
}

function addRect(slide, name, left, top, width, height, fill) {
  return slide.shapes.add({
    geometry: "rect",
    name,
    position: { left, top, width, height },
    fill,
    line: { style: "solid", fill: "none", width: 0 },
  });
}

function addCustomPolygon(slide, name, left, top, width, height, points, fill) {
  const commands = [{ moveTo: points[0] }];
  for (const point of points.slice(1)) commands.push({ lineTo: point });
  commands.push({ close: {} });
  return slide.shapes.add({
    geometry: "custom",
    name,
    position: { left, top, width, height },
    fill,
    line: { style: "solid", fill: "none", width: 0 },
    customPaths: [{ width, height, commands }],
  });
}

function addSecondaryCallout(slide, item) {
  const marker = slide.shapes.add({
    geometry: "ellipse",
    name: `${item.name}-number-marker`,
    position: { left: item.markerLeft, top: item.top + 7, width: 38, height: 38 },
    fill: C.purple,
    line: { style: "solid", fill: C.purple, width: 1 },
    shadow: "0px 4px 10px #7030A0/16",
  });
  marker.text = item.number;
  marker.text.style = {
    fontSize: 16,
    color: C.mint,
    bold: true,
    alignment: "center",
    verticalAlignment: "middle",
    typeface: "Aptos Display",
    insets: { top: 0, right: 0, bottom: 0, left: 0 },
  };

  addText(slide, {
    name: `${item.name}-heading`,
    text: item.heading,
    left: item.textLeft,
    top: item.top,
    width: item.textWidth,
    height: 30,
    fontSize: 24,
    bold: true,
    color: C.ink,
    alignment: item.alignment,
  });
  addText(slide, {
    name: `${item.name}-descriptor`,
    text: "Short supporting lens",
    left: item.textLeft,
    top: item.top + 32,
    width: item.textWidth,
    height: 23,
    fontSize: 16,
    color: C.muted,
    alignment: item.alignment,
    typeface: "Aptos",
  });

  const accentLeft = item.alignment === "right"
    ? item.textLeft + item.textWidth - 50
    : item.textLeft;
  addRect(slide, `${item.name}-accent`, accentLeft, item.top + 61, 50, 3, C.mint);
}

async function main() {
  await fs.mkdir(BUILD, { recursive: true });

  const deck = Presentation.create({ slideSize: { width: 1280, height: 720 } });
  const slide = deck.slides.add();
  slide.background.fill = C.white;

  // Recreated from the supplied slide layout as editable native geometry.
  addCustomPolygon(
    slide,
    "reference-mint-corner",
    0,
    0,
    360,
    352,
    [
      { x: 0, y: 68 },
      { x: 72, y: 0 },
      { x: 360, y: 0 },
      { x: 0, y: 352 },
    ],
    C.mint,
  );
  addCustomPolygon(
    slide,
    "reference-mint-hairline",
    16,
    134,
    270,
    270,
    [
      { x: 0, y: 270 },
      { x: 2, y: 270 },
      { x: 270, y: 2 },
      { x: 270, y: 0 },
    ],
    C.mint,
  );
  addCustomPolygon(
    slide,
    "reference-purple-corner",
    902,
    336,
    378,
    384,
    [
      { x: 0, y: 384 },
      { x: 290, y: 384 },
      { x: 378, y: 273 },
      { x: 378, y: 0 },
    ],
    C.purple,
  );
  addCustomPolygon(
    slide,
    "reference-purple-hairline",
    1002,
    300,
    262,
    262,
    [
      { x: 0, y: 262 },
      { x: 2, y: 262 },
      { x: 262, y: 2 },
      { x: 262, y: 0 },
    ],
    C.purple,
  );

  // Title lives in the clear white field, respecting the corner geometry.
  addText(slide, {
    name: "slide-title",
    text: "Seven ways to frame one idea",
    left: 382,
    top: 42,
    width: 710,
    height: 52,
    fontSize: 36,
    bold: true,
    color: C.ink,
  });
  addText(slide, {
    name: "slide-kicker",
    text: "RADIAL MAP  •  01",
    left: 1060,
    top: 56,
    width: 162,
    height: 26,
    fontSize: 16,
    color: C.purple,
    bold: true,
    alignment: "right",
    typeface: "Aptos",
  });
  addRect(slide, "title-rule", 382, 103, 170, 4, C.mint);

  // Subtle radial field on the white canvas.
  slide.shapes.add({
    geometry: "ellipse",
    name: "radial-wash",
    position: { left: 486, top: 183, width: 308, height: 308 },
    fill: "radial(#7030A0/10 0%, #7030A0/4 58%, #7030A0/0 100%)",
    line: { style: "solid", fill: "none", width: 0 },
  });
  slide.shapes.add({
    geometry: "ellipse",
    name: "outer-orbit",
    position: { left: 512, top: 209, width: 256, height: 256 },
    fill: "none",
    line: { style: "dashed", fill: "#7030A0/22", width: 1.2 },
  });

  // Routing anchors are created first so connectors remain behind visible nodes.
  const centerAnchor = slide.shapes.add({
    geometry: "ellipse",
    name: "center-routing-anchor",
    position: { left: 545, top: 242, width: 190, height: 190 },
    fill: "transparent",
    line: { style: "solid", fill: "none", width: 0 },
  });
  const anchorData = [
    { name: "direction-01-anchor", left: 478, top: 187, fromSide: "left", toSide: "right" },
    { name: "direction-02-anchor", left: 362, top: 325, fromSide: "left", toSide: "right" },
    { name: "direction-03-anchor", left: 416, top: 463, fromSide: "left", toSide: "right" },
    { name: "direction-04-anchor", left: 796, top: 187, fromSide: "right", toSide: "left" },
    { name: "direction-05-anchor", left: 868, top: 325, fromSide: "right", toSide: "left" },
    { name: "direction-06-anchor", left: 818, top: 463, fromSide: "right", toSide: "left" },
  ].map((item) => ({
    ...item,
    shape: slide.shapes.add({
      geometry: "ellipse",
      name: item.name,
      position: { left: item.left, top: item.top, width: 8, height: 8 },
      fill: "transparent",
      line: { style: "solid", fill: "none", width: 0 },
    }),
  }));
  const priorityAnchor = slide.shapes.add({
    geometry: "ellipse",
    name: "priority-routing-anchor",
    position: { left: 636, top: 528, width: 8, height: 8 },
    fill: "transparent",
    line: { style: "solid", fill: "none", width: 0 },
  });

  for (const anchor of anchorData) {
    slide.shapes.connect(centerAnchor, anchor.shape, {
      kind: "straight",
      fromSide: anchor.fromSide,
      toSide: anchor.toSide,
      line: { style: "solid", fill: "#7030A0/58", width: 2 },
      head: { type: "triangle", width: "sm", length: "sm" },
      cap: "round",
    });
  }
  slide.shapes.connect(centerAnchor, priorityAnchor, {
    kind: "straight",
    fromSide: "bottom",
    toSide: "top",
    line: { style: "solid", fill: C.mint, width: 5 },
    head: { type: "triangle", width: "med", length: "med" },
    cap: "round",
  });

  // Visible connector endpoints.
  for (const anchor of anchorData) {
    slide.shapes.add({
      geometry: "ellipse",
      name: anchor.name.replace("anchor", "endpoint"),
      position: { left: anchor.left - 3, top: anchor.top - 3, width: 14, height: 14 },
      fill: C.mint,
      line: { style: "solid", fill: C.purple, width: 2.5 },
      shadow: "0px 3px 8px #7030A0/18",
    });
  }
  slide.shapes.add({
    geometry: "ellipse",
    name: "priority-endpoint",
    position: { left: 631, top: 523, width: 18, height: 18 },
    fill: C.mint,
    line: { style: "solid", fill: C.purple, width: 3 },
    shadow: "0px 3px 8px #7030A0/20",
  });

  const callouts = [
    { name: "direction-01", number: "01", heading: "DIRECTION 01", top: 149, textLeft: 222, textWidth: 194, markerLeft: 428, alignment: "right" },
    { name: "direction-02", number: "02", heading: "DIRECTION 02", top: 287, textLeft: 48, textWidth: 246, markerLeft: 308, alignment: "right" },
    { name: "direction-03", number: "03", heading: "DIRECTION 03", top: 425, textLeft: 98, textWidth: 252, markerLeft: 362, alignment: "right" },
    { name: "direction-04", number: "04", heading: "DIRECTION 04", top: 149, textLeft: 872, textWidth: 220, markerLeft: 820, alignment: "left" },
    { name: "direction-05", number: "05", heading: "DIRECTION 05", top: 287, textLeft: 946, textWidth: 240, markerLeft: 894, alignment: "left" },
    { name: "direction-06", number: "06", heading: "DIRECTION 06", top: 425, textLeft: 896, textWidth: 220, markerLeft: 844, alignment: "left" },
  ];
  for (const callout of callouts) addSecondaryCallout(slide, callout);

  // One-word center node.
  slide.shapes.add({
    geometry: "ellipse",
    name: "center-halo",
    position: { left: 532, top: 229, width: 216, height: 216 },
    fill: "none",
    line: { style: "solid", fill: "#66FF99/52", width: 2 },
  });
  const center = slide.shapes.add({
    geometry: "ellipse",
    name: "center-word-node",
    position: { left: 545, top: 242, width: 190, height: 190 },
    fill: "linear(135deg, #7030A0 0%, #552178 100%)",
    line: { style: "solid", fill: C.mint, width: 4 },
    shadow: "0px 12px 26px #7030A0/24",
  });
  center.text = "CORE IDEA\nNEXUS";
  center.text.style = {
    fontSize: 30,
    color: C.white,
    bold: true,
    alignment: "center",
    verticalAlignment: "middle",
    typeface: "Aptos Display",
    lineSpacing: 1,
    autoFit: "shrinkText",
    insets: { top: 15, right: 14, bottom: 15, left: 14 },
  };
  center.text.get("CORE IDEA").style = {
    fontSize: 16,
    bold: true,
    color: C.mint,
  };

  // The seventh direction is the dominant bottom-center destination.
  slide.shapes.add({
    geometry: "roundRect",
    name: "priority-shadow-field",
    position: { left: 427, top: 564, width: 426, height: 108 },
    fill: "#7030A0/10",
    line: { style: "solid", fill: "none", width: 0 },
    borderRadius: 22,
  });
  slide.shapes.add({
    geometry: "roundRect",
    name: "priority-card",
    position: { left: 439, top: 576, width: 402, height: 86 },
    fill: "linear(0deg, #7030A0 0%, #5C2482 100%)",
    line: { style: "solid", fill: C.mint, width: 3 },
    borderRadius: 19,
    shadow: "0px 10px 22px #7030A0/22",
  });
  const primaryMarker = slide.shapes.add({
    geometry: "ellipse",
    name: "direction-07-number-marker",
    position: { left: 458, top: 590, width: 58, height: 58 },
    fill: C.mint,
    line: { style: "solid", fill: C.mint, width: 1 },
  });
  primaryMarker.text = "07";
  primaryMarker.text.style = {
    fontSize: 23,
    color: C.purple,
    bold: true,
    alignment: "center",
    verticalAlignment: "middle",
    typeface: "Aptos Display",
    insets: { top: 0, right: 0, bottom: 0, left: 0 },
  };
  addText(slide, {
    name: "priority-eyebrow",
    text: "PRIORITY DIRECTION",
    left: 539,
    top: 589,
    width: 270,
    height: 19,
    fontSize: 16,
    color: C.mint,
    bold: true,
    typeface: "Aptos",
  });
  addText(slide, {
    name: "priority-heading",
    text: "MAKE IT UNMISSABLE",
    left: 539,
    top: 608,
    width: 270,
    height: 36,
    fontSize: 27,
    color: C.white,
    bold: true,
  });
  addRect(slide, "priority-edge", 823, 592, 4, 54, C.mint);

  slide.speakerNotes.textFrame.setText([
    "Template usage: Replace NEXUS, DIRECTION 01–06, and the priority direction. Preserve the emphasized seventh path at bottom center.",
    "Color system: mint #66FF99 and purple #7030A0.",
    "[Sources]",
    `- User-provided layout reference: ${REFERENCE} (visual layout adaptation only; not embedded).`,
    "- No external claims or third-party assets.",
  ]);
  slide.speakerNotes.setVisible(true);

  await writeBlob(`${BUILD}\\slide-1.png`, await deck.export({ slide, format: "png", scale: 2 }));
  await fs.writeFile(`${BUILD}\\slide-1.layout.json`, await (await slide.export({ format: "layout" })).text());
  await writeBlob(`${BUILD}\\deck-montage.webp`, await deck.export({ format: "webp", montage: true, scale: 1 }));
  const inspection = await deck.inspect({ kind: "slide,textbox,shape,notes", maxChars: 18000 });
  await fs.writeFile(`${BUILD}\\inspection.ndjson`, inspection.ndjson);

  const pptx = await PresentationFile.exportPptx(deck);
  await pptx.save(OUTPUT);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
