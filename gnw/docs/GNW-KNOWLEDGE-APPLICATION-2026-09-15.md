# GNW Knowledge Application — 2026-09-15

یہ branch GNW knowledge collection سے صرف وہی کم خطرہ، قابلِ جانچ اضافہ لاتی ہے جو exact remote Phase 4 source کے ساتھ compare کیا گیا ہے۔ Historical ZIPs کو blind merge نہیں کیا گیا۔

## شامل تبدیلی

`src/server/phase-one-tools.ts` میں GNW کے پہلے 20 governed tools کا status registry اور priority contract شامل کیا گیا ہے۔ `tests/phase-one-tools.test.ts` rank uniqueness، P0 safety ordering، اور status summary کو verify کرتا ہے۔ یہ registry production certification کا دعویٰ نہیں کرتی۔

## Evidence boundary

Source base: `7f408afc7e5feadc1649cc44e75ba8b2c0c5d162`۔ Baseline `npm ci`، `npm run typecheck` اور existing Phase 4 targeted tests پہلے PASS ہوئے۔ Historical source comparisons میں consolidated canonical source کے 203/203 files exact MATCH ہوئے؛ پرانے Phase One اور Remediated bundles کے مختلف files کو automatically merge نہیں کیا گیا۔

## باقی غیر لاگو material

Historical executor/provider implementations، old package locks، generated Python bytecode، اور evidence-only documents کو اس branch میں نہیں ملایا گیا، کیونکہ ان کی current source سے compatibility یا production value الگ test کے بغیر ثابت نہیں ہوئی۔
