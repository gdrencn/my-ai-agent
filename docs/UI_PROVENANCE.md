Screen / Selection / text helpers are derived from gdrencn/my-ai-sandbox stable 0.2.25. Business-specific container/shell helpers are excluded. Rendering, keys and input editing remain shared within maa.

The 0.1.3 adaptation adds styled title/value cells and preserves those styles while wrapping descriptions. Grouped business menus call the same Manager as CLI; no host/global instructions are packaged in the product.

The 0.1.7 adaptation keeps readonly activation inside the current prompt and adds wrapped focus details to model selection. Lifecycle decisions remain in Manager, shared by menu and CLI. Global instruction and style files are not modified by this project.

The 0.2.1 adaptation adds optional masked input to the same Screen.input control, retaining cursor editing and terminal restoration. IM menus reuse Screen, existing title/value styling and shared output/progress; their operations are shared with maa im. No separate terminal renderer is added.
