import fs from "node:fs/promises";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const OUTPUT = "C:\\Users\\User\\Desktop\\Combined_Predictions\\Seven_Directions_Radial_Template.pptx";
const BUILD = "C:\\Users\\User\\Desktop\\Combined_Predictions\\.tmp_seven_directions_template";

const COLORS = {
  mint: "#66FF99",
  purple: "#7030A0",
  background: "#0F0914",
  white: "#F9F5FC",
  muted: "#CBBFD3",
  faint: "#716578",
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
  color = COLORS.white,
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

function addFlatLine(slide, name, left, top, width, color, height = 2) {
  return slide.shapes.add({
    geometry: "rect",
    name,
    position: { left, top, width, height },
    fill: color,
    line: { style: "solid", fill: "none", width: 0 },
  });
}

function addSecondaryCallout(slide, item) {
  const marker = slide.shapes.add({
    geometry: "ellipse",
    name: `${item.name}-number-marker`,
    position: { left: item.markerLeft, top: item.top + 9, width: 38, height: 38 },
    fill: "#7030A0/22",
    line: { style: "solid", fill: "#7030A0", width: 1.5 },
  });
  marker.text = item.number;
  marker.text.style = {
    fontSize: 16,
    color: COLORS.mint,
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
    height: 32,
    fontSize: 24,
    bold: true,
    alignment: item.alignment,
  });
  addText(slide, {
    name: `${item.name}-descriptor`,
    text: "Short supporting lens",
    left: item.textLeft,
    top: item.top + 34,
    width: item.textWidth,
    height: 24,
    fontSize: 16,
    color: COLORS.muted,
    alignment: item.alignment,
    typeface: "Aptos",
  });
  const lineLeft = item.alignment === "right"
    ? item.textLeft + item.textWidth - 52
    : item.textLeft;
  addFlatLine(slide, `${item.name}-accent-rule`, lineLeft, item.top + 64, 52, "#66FF99/78", 2);
}

async function main() {
  await fs.mkdir(BUILD, { recursive: true });

  const deck = Presentation.create({
    slideSize: { width: 1280, height: 720 },
  });
  const slide = deck.slides.add();
  slide.background.fill = "linear(135deg, #0F0914 0%, #18101D 58%, #0B0810 100%)";

  // Header hierarchy.
  addFlatLine(slide, "title-accent", 62, 52, 6, COLORS.mint, 48);
  addText(slide, {
    name: "slide-title",
    text: "Seven ways to frame one idea",
    left: 88,
    top: 49,
    width: 700,
    height: 52,
    fontSize: 36,
    bold: true,
  });
  addText(slide, {
    name: "slide-kicker",
    text: "RADIAL PRIORITY MAP  •  01",
    left: 944,
    top: 62,
    width: 274,
    height: 28,
    fontSize: 16,
    color: COLORS.mint,
    bold: true,
    alignment: "right",
    typeface: "Aptos",
  });
  addFlatLine(slide, "header-rule", 62, 112, 1156, "#7030A0/32", 1);

  // The radial field is deliberately quiet so the words remain the visual payload.
  slide.shapes.add({
    geometry: "ellipse",
    name: "radial-glow",
    position: { left: 418, top: 151, width: 444, height: 444 },
    fill: "radial(#7030A0/24 0%, #7030A0/8 56%, #7030A0/0 100%)",
    line: { style: "solid", fill: "none", width: 0 },
  });
  slide.shapes.add({
    geometry: "ellipse",
    name: "outer-orbit",
    position: { left: 446, top: 178, width: 388, height: 388 },
    fill: "none",
    line: { style: "dashed", fill: "#7030A0/28", width: 1.2 },
  });
  slide.shapes.add({
    geometry: "ellipse",
    name: "inner-orbit",
    position: { left: 494, top: 226, width: 292, height: 292 },
    fill: "none",
    line: { style: "solid", fill: "#66FF99/18", width: 1 },
  });

  // Invisible routing anchors allow the connectors to sit behind every visible node.
  const centerAnchor = slide.shapes.add({
    geometry: "ellipse",
    name: "center-routing-anchor",
    position: { left: 531, top: 257, width: 218, height: 218 },
    fill: "transparent",
    line: { style: "solid", fill: "none", width: 0 },
  });

  const anchors = [
    { name: "direction-01-anchor", left: 346, top: 191, side: "left", toSide: "right" },
    { name: "direction-02-anchor", left: 322, top: 331, side: "left", toSide: "right" },
    { name: "direction-03-anchor", left: 350, top: 471, side: "left", toSide: "right" },
    { name: "direction-04-anchor", left: 928, top: 191, side: "right", toSide: "left" },
    { name: "direction-05-anchor", left: 952, top: 331, side: "right", toSide: "left" },
    { name: "direction-06-anchor", left: 924, top: 471, side: "right", toSide: "left" },
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
    position: { left: 636, top: 541, width: 8, height: 8 },
    fill: "transparent",
    line: { style: "solid", fill: "none", width: 0 },
  });

  for (const anchor of anchors) {
    slide.shapes.connect(centerAnchor, anchor.shape, {
      kind: "straight",
      fromSide: anchor.side,
      toSide: anchor.toSide,
      line: { style: "solid", fill: "#7030A0/68", width: 2 },
      head: { type: "triangle", width: "sm", length: "sm" },
      cap: "round",
    });
  }
  slide.shapes.connect(centerAnchor, priorityAnchor, {
    kind: "straight",
    fromSide: "bottom",
    toSide: "top",
    line: { style: "solid", fill: COLORS.mint, width: 5 },
    head: { type: "triangle", width: "med", length: "med" },
    cap: "round",
  });

  // Visible endpoint nodes.
  for (const anchor of anchors) {
    slide.shapes.add({
      geometry: "ellipse",
      name: anchor.name.replace("anchor", "endpoint"),
      position: { left: anchor.left - 3, top: anchor.top - 3, width: 14, height: 14 },
      fill: COLORS.mint,
      line: { style: "solid", fill: "#0F0914", width: 3 },
      shadow: "shadow-sm",
    });
  }
  slide.shapes.add({
    geometry: "ellipse",
    name: "priority-endpoint",
    position: { left: 631, top: 536, width: 18, height: 18 },
    fill: COLORS.mint,
    line: { style: "solid", fill: "#0F0914", width: 4 },
    shadow: "shadow-md",
  });

  // Six balanced secondary perspectives.
  const callouts = [
    { name: "direction-01", number: "01", heading: "DIRECTION 01", top: 153, textLeft: 62, textWidth: 220, markerLeft: 296, alignment: "right" },
    { name: "direction-02", number: "02", heading: "DIRECTION 02", top: 293, textLeft: 38, textWidth: 244, markerLeft: 296, alignment: "right" },
    { name: "direction-03", number: "03", heading: "DIRECTION 03", top: 433, textLeft: 66, textWidth: 216, markerLeft: 296, alignment: "right" },
    { name: "direction-04", number: "04", heading: "DIRECTION 04", top: 153, textLeft: 998, textWidth: 220, markerLeft: 944, alignment: "left" },
    { name: "direction-05", number: "05", heading: "DIRECTION 05", top: 293, textLeft: 998, textWidth: 244, markerLeft: 944, alignment: "left" },
    { name: "direction-06", number: "06", heading: "DIRECTION 06", top: 433, textLeft: 998, textWidth: 216, markerLeft: 944, alignment: "left" },
  ];
  for (const callout of callouts) addSecondaryCallout(slide, callout);

  // Center node: one word/short phrase, fully editable.
  slide.shapes.add({
    geometry: "ellipse",
    name: "center-halo",
    position: { left: 518, top: 244, width: 244, height: 244 },
    fill: "none",
    line: { style: "solid", fill: "#66FF99/46", width: 2 },
  });
  const center = slide.shapes.add({
    geometry: "ellipse",
    name: "center-word-node",
    position: { left: 535, top: 261, width: 210, height: 210 },
    fill: "linear(135deg, #7030A0 0%, #4A1C66 100%)",
    line: { style: "solid", fill: COLORS.mint, width: 3.5 },
    shadow: "0px 16px 38px #000000/40",
  });
  center.text = "CORE IDEA\nNEXUS";
  center.text.style = {
    fontSize: 31,
    color: COLORS.white,
    bold: true,
    alignment: "center",
    verticalAlignment: "middle",
    typeface: "Aptos Display",
    lineSpacing: 1.02,
    autoFit: "shrinkText",
    insets: { top: 18, right: 16, bottom: 18, left: 16 },
  };
  center.text.get("CORE IDEA").style = {
    fontSize: 16,
    bold: true,
    color: COLORS.mint,
  };

  // The seventh path is deliberately larger, brighter, and placed on the visual axis.
  slide.shapes.add({
    geometry: "roundRect",
    name: "priority-glow",
    position: { left: 411, top: 561, width: 458, height: 118 },
    fill: "#66FF99/12",
    line: { style: "solid", fill: "none", width: 0 },
    borderRadius: 26,
    shadow: "0px 12px 34px #66FF99/18",
  });
  slide.shapes.add({
    geometry: "roundRect",
    name: "priority-card",
    position: { left: 424, top: 574, width: 432, height: 92 },
    fill: "linear(0deg, #66FF99 0%, #A4FFBF 100%)",
    line: { style: "solid", fill: COLORS.mint, width: 1 },
    borderRadius: 22,
    shadow: "0px 10px 28px #000000/34",
  });
  const primaryMarker = slide.shapes.add({
    geometry: "ellipse",
    name: "direction-07-number-marker",
    position: { left: 445, top: 590, width: 60, height: 60 },
    fill: COLORS.purple,
    line: { style: "solid", fill: COLORS.purple, width: 1 },
  });
  primaryMarker.text = "07";
  primaryMarker.text.style = {
    fontSize: 24,
    color: COLORS.mint,
    bold: true,
    alignment: "center",
    verticalAlignment: "middle",
    typeface: "Aptos Display",
    insets: { top: 0, right: 0, bottom: 0, left: 0 },
  };
  addText(slide, {
    name: "priority-eyebrow",
    text: "PRIORITY DIRECTION",
    left: 530,
    top: 586,
    width: 290,
    height: 20,
    fontSize: 16,
    color: COLORS.purple,
    bold: true,
    typeface: "Aptos",
  });
  addText(slide, {
    name: "priority-heading",
    text: "MAKE IT UNMISSABLE",
    left: 530,
    top: 607,
    width: 292,
    height: 38,
    fontSize: 28,
    color: COLORS.purple,
    bold: true,
  });
  addFlatLine(slide, "priority-edge", 844, 592, 4, COLORS.purple, 56);

  slide.speakerNotes.textFrame.setText([
    "Template usage: Replace NEXUS, DIRECTION 01–06, and the priority direction. Keep the seventh path at bottom center to preserve the intended emphasis.",
    "Color system: primary mint #66FF99; primary purple #7030A0; neutral tones support contrast.",
    "[Sources]",
    "- No external sources or assets; original editable layout.",
  ]);
  slide.speakerNotes.setVisible(true);

  const png = await deck.export({ slide, format: "png", scale: 2 });
  await writeBlob(`${BUILD}\\slide-1.png`, png);
  const layout = await slide.export({ format: "layout" });
  await fs.writeFile(`${BUILD}\\slide-1.layout.json`, await layout.text());
  const montage = await deck.export({ format: "webp", montage: true, scale: 1 });
  await writeBlob(`${BUILD}\\deck-montage.webp`, montage);
  const inspection = await deck.inspect({
    kind: "slide,textbox,shape,notes",
    maxChars: 16000,
  });
  await fs.writeFile(`${BUILD}\\inspection.ndjson`, inspection.ndjson);

  const pptx = await PresentationFile.exportPptx(deck);
  await pptx.save(OUTPUT);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
