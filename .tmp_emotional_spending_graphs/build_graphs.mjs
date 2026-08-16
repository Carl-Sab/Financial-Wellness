import fs from "node:fs/promises";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const OUTPUT = "C:\\Users\\User\\Desktop\\Combined_Predictions\\Emotional_Spending_Survey_Graphs.pptx";
const BUILD = "C:\\Users\\User\\Desktop\\Combined_Predictions\\.tmp_emotional_spending_graphs";

const C = {
  mint: "#66FF99",
  purple: "#7030A0",
  ink: "#2E173D",
  muted: "#746C79",
  grid: "#E7DCEC",
  pale: "#F7F2FA",
  white: "#FFFFFF",
};

const SOURCES = {
  lendingTree: "https://www.lendingtree.com/credit-cards/study/emotional-shopping/",
  creditKarma: "https://www.creditkarma.com/about/commentary/emotional-spending-is-out-of-control-for-more-than-one-third-of-gen-z-study-finds",
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
    customPaths: [{ id: `${name}-path`, width, height, commands }],
  });
}

function addThemeFrame(slide, slideNo) {
  slide.background.fill = C.white;

  addCustomPolygon(
    slide,
    `mint-corner-${slideNo}`,
    0,
    0,
    300,
    272,
    [
      { x: 0, y: 58 },
      { x: 62, y: 0 },
      { x: 300, y: 0 },
      { x: 0, y: 272 },
    ],
    C.mint,
  );
  addCustomPolygon(
    slide,
    `mint-hairline-${slideNo}`,
    20,
    112,
    248,
    248,
    [
      { x: 0, y: 248 },
      { x: 2, y: 248 },
      { x: 248, y: 2 },
      { x: 248, y: 0 },
    ],
    C.mint,
  );
  addCustomPolygon(
    slide,
    `purple-corner-${slideNo}`,
    1040,
    486,
    240,
    234,
    [
      { x: 0, y: 234 },
      { x: 178, y: 234 },
      { x: 240, y: 166 },
      { x: 240, y: 0 },
    ],
    C.purple,
  );
  addCustomPolygon(
    slide,
    `purple-hairline-${slideNo}`,
    1080,
    395,
    184,
    184,
    [
      { x: 0, y: 184 },
      { x: 2, y: 184 },
      { x: 184, y: 2 },
      { x: 184, y: 0 },
    ],
    C.purple,
  );

  addText(slide, {
    name: `corner-label-${slideNo}`,
    text: "SURVEY",
    left: 64,
    top: 70,
    width: 122,
    height: 23,
    fontSize: 16,
    color: C.purple,
    bold: true,
    typeface: "Aptos",
  });
  addText(slide, {
    name: `corner-number-${slideNo}`,
    text: `0${slideNo}`,
    left: 62,
    top: 92,
    width: 122,
    height: 52,
    fontSize: 46,
    color: C.purple,
    bold: true,
  });
}

function addBarChart(slide, {
  name,
  categories,
  values,
  points,
  top,
  height,
}) {
  return slide.charts.add("bar", {
    name,
    position: { left: 150, top, width: 930, height },
    categories,
    series: [{
      name: "Share of respondents",
      values,
      valuesFormatCode: "0%",
      fill: C.purple,
      line: { style: "solid", fill: C.purple, width: 1 },
      points,
    }],
    barOptions: {
      direction: "bar",
      grouping: "clustered",
      gapWidth: 42,
      varyColors: false,
    },
    hasLegend: false,
    xAxis: {
      visible: true,
      min: 0,
      max: 1,
      majorUnit: 0.2,
      numberFormatCode: "0%",
      tickLabelPosition: "nextTo",
      textStyle: { fill: C.muted, fontSize: 14 },
      line: { style: "solid", fill: C.grid, width: 1 },
      majorGridlines: { style: "solid", fill: C.grid, width: 1 },
      minorGridlines: null,
    },
    yAxis: {
      visible: true,
      tickLabelPosition: "nextTo",
      labelOffsetPercent: 95,
      textStyle: { fill: C.ink, fontSize: 16, bold: true },
      line: { style: "solid", fill: C.white, width: 0 },
      majorGridlines: null,
      minorGridlines: null,
    },
    dataLabels: {
      showValue: true,
      position: "outEnd",
      textStyle: { fill: C.ink, fontSize: 18, bold: true },
      fill: "none",
      line: { style: "solid", fill: "none", width: 0 },
    },
    chartFill: "none",
    chartLine: { style: "solid", fill: "none", width: 0 },
    plotAreaFill: "none",
    plotAreaLine: { style: "solid", fill: "none", width: 0 },
  });
}

async function main() {
  await fs.mkdir(BUILD, { recursive: true });
  const deck = Presentation.create({ slideSize: { width: 1280, height: 720 } });

  // Slide 1 — LendingTree / QuestionPro, 2025.
  const slide1 = deck.slides.add();
  addThemeFrame(slide1, 1);
  addText(slide1, {
    name: "slide-1-title",
    text: "Emotional shopping often ends in overspending",
    left: 340,
    top: 40,
    width: 700,
    height: 56,
    fontSize: 36,
    color: C.ink,
    bold: true,
  });
  addText(slide1, {
    name: "slide-1-subtitle",
    text: "2025 U.S. survey  |  n=2,000 adults  |  LendingTree / QuestionPro",
    left: 340,
    top: 96,
    width: 720,
    height: 26,
    fontSize: 16,
    color: C.muted,
    typeface: "Aptos",
  });
  addRect(slide1, "slide-1-title-rule", 340, 133, 178, 4, C.mint);

  addBarChart(slide1, {
    name: "lendingtree-emotional-shopping-chart",
    top: 160,
    height: 400,
    // Reversed input yields the intended top-to-bottom order in a horizontal bar chart.
    categories: [
      "Emotional shoppers · Financial well-being hurt",
      "Emotional shoppers · Regretted it",
      "Emotional shoppers · Overspent",
      "All adults · Shopped to improve mood",
      "All adults · Emotions influence purchases",
    ],
    values: [0.44, 0.69, 0.74, 0.47, 0.63],
    points: [
      { idx: 0, fill: "#7030A0/48", line: { style: "solid", fill: C.purple, width: 1 } },
      { idx: 1, fill: C.purple, line: { style: "solid", fill: C.purple, width: 1 } },
      { idx: 2, fill: C.mint, line: { style: "solid", fill: C.purple, width: 1.5 } },
      { idx: 3, fill: "#7030A0/68", line: { style: "solid", fill: C.purple, width: 1 } },
      { idx: 4, fill: "#7030A0/86", line: { style: "solid", fill: C.purple, width: 1 } },
    ],
  });

  addRect(slide1, "slide-1-insight-rule", 340, 585, 6, 50, C.mint);
  addText(slide1, {
    name: "slide-1-insight",
    text: "Among emotional shoppers, overspending is the most common reported consequence.",
    left: 362,
    top: 582,
    width: 660,
    height: 56,
    fontSize: 20,
    color: C.ink,
    bold: true,
  });
  addText(slide1, {
    name: "slide-1-source-footer",
    text: "Base note: 63% and 47% are all adults; 74%, 69%, and 44% are emotional shoppers.",
    left: 72,
    top: 675,
    width: 900,
    height: 22,
    fontSize: 16,
    color: C.muted,
    typeface: "Aptos",
  });
  slide1.speakerNotes.textFrame.setText([
    "The first two bars use the full U.S. adult sample. The three consequence bars use the emotional-shopper subgroup.",
    "Methodology: LendingTree commissioned QuestionPro to survey 2,000 U.S. consumers ages 18 to 79 online from June 2–3, 2025; nonprobability sample with quotas and quality-control review.",
    "[Sources]",
    `- ${SOURCES.lendingTree}`,
  ]);
  slide1.speakerNotes.setVisible(true);

  // Slide 2 — Credit Karma / Qualtrics, 2023.
  const slide2 = deck.slides.add();
  addThemeFrame(slide2, 2);
  addText(slide2, {
    name: "slide-2-title",
    text: "Regret is common—and most want to spend less",
    left: 340,
    top: 40,
    width: 700,
    height: 56,
    fontSize: 36,
    color: C.ink,
    bold: true,
  });
  addText(slide2, {
    name: "slide-2-subtitle",
    text: "2023 U.S. survey  |  n=1,008 adults  |  Credit Karma / Qualtrics",
    left: 340,
    top: 96,
    width: 720,
    height: 26,
    fontSize: 16,
    color: C.muted,
    typeface: "Aptos",
  });
  addRect(slide2, "slide-2-title-rule", 340, 133, 178, 4, C.mint);

  addBarChart(slide2, {
    name: "creditkarma-emotional-spending-chart",
    top: 190,
    height: 330,
    categories: [
      "Emotional spending feels out of control",
      "Experienced buyer’s remorse",
      "Want to reduce their spending",
    ],
    values: [0.24, 0.45, 0.59],
    points: [
      { idx: 0, fill: "#7030A0/60", line: { style: "solid", fill: C.purple, width: 1 } },
      { idx: 1, fill: C.purple, line: { style: "solid", fill: C.purple, width: 1 } },
      { idx: 2, fill: C.mint, line: { style: "solid", fill: C.purple, width: 1.5 } },
    ],
  });

  addRect(slide2, "slide-2-insight-rule", 340, 550, 6, 58, C.mint);
  addText(slide2, {
    name: "slide-2-insight",
    text: "The desire to cut back is more than twice the share calling their spending “out of control.”",
    left: 362,
    top: 546,
    width: 675,
    height: 66,
    fontSize: 20,
    color: C.ink,
    bold: true,
  });
  addText(slide2, {
    name: "slide-2-source-footer",
    text: "All three figures are reported for the U.S. adult survey sample.",
    left: 72,
    top: 675,
    width: 780,
    height: 22,
    fontSize: 16,
    color: C.muted,
    typeface: "Aptos",
  });
  slide2.speakerNotes.textFrame.setText([
    "Methodology: Qualtrics surveyed 1,008 U.S. adults ages 18 and older online on behalf of Credit Karma from February 22–27, 2023.",
    "The ‘more than twice’ statement is an arithmetic comparison of 59% versus 24%.",
    "[Sources]",
    `- ${SOURCES.creditKarma}`,
  ]);
  slide2.speakerNotes.setVisible(true);

  for (const [index, slide] of deck.slides.items.entries()) {
    const stem = `slide-${String(index + 1).padStart(2, "0")}`;
    await writeBlob(`${BUILD}\\${stem}.png`, await deck.export({ slide, format: "png", scale: 2 }));
    await fs.writeFile(`${BUILD}\\${stem}.layout.json`, await (await slide.export({ format: "layout" })).text());
  }
  await writeBlob(`${BUILD}\\deck-montage.webp`, await deck.export({ format: "webp", montage: true, scale: 1 }));
  const inspection = await deck.inspect({ kind: "slide,textbox,shape,chart,notes", maxChars: 24000 });
  await fs.writeFile(`${BUILD}\\inspection.ndjson`, inspection.ndjson);

  const pptx = await PresentationFile.exportPptx(deck);
  await pptx.save(OUTPUT);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
