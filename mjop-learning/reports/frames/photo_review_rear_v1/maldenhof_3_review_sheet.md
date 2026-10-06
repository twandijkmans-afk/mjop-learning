# Review sheet maldenhof_3.jpg (rear annotation v1)

Handmatige visuele lezing door Claude; alle kandidaten REVIEW_REQUIRED, human decision PENDING. bbox = genormaliseerde beeldcoordinaten, geen maten. Dit is GEEN gebouwtotaal en er zijn geen frame instances. Foto 3 is de achterzijde; bag_pand_id = null (adres/pand niet bewezen).

| Candidate ID | Type | Storey | Visibility | bbox_norm | Parent | Relation review | Human decision |
|---|---|---|---|---|---|---|---|
| FC-M3-001 | UNKNOWN_OPENING | UNKNOWN | HEAVILY_OCCLUDED | [0.15, 0.67, 0.245, 0.71] | - | - | PENDING |
| FC-M3-002 | UNKNOWN_OPENING | UNKNOWN | HEAVILY_OCCLUDED | [0.15, 0.7333, 0.1975, 0.7733] | - | - | PENDING |
| FC-M3-003 | WINDOW | UNKNOWN | PARTIAL | [0.273, 0.6733, 0.3325, 0.746] | - | - | PENDING |
| FC-M3-004 | EXTERIOR_DOOR | UNKNOWN | PARTIAL | [0.616, 0.63, 0.6715, 0.7] | - | REL-M3-001 | PENDING |
| FC-M3-005 | WINDOW | UNKNOWN | FULL | [0.673, 0.6147, 0.7945, 0.7] | - | REL-M3-001 | PENDING |
| FC-M3-006 | ROOF_WINDOW | ROOF | PARTIAL | [0.0, 0.5967, 0.0435, 0.6333] | - | - | PENDING |
| FC-M3-007 | ROOF_WINDOW | ROOF | FULL | [0.033, 0.582, 0.087, 0.6267] | - | - | PENDING |
| FC-M3-008 | ROOF_WINDOW | ROOF | FULL | [0.235, 0.524, 0.31, 0.5933] | - | - | PENDING |
| FC-M3-009 | ROOF_WINDOW | ROOF | FULL | [0.764, 0.384, 0.834, 0.4667] | - | - | PENDING |
| FC-M3-010 | DORMER_WINDOW | ROOF | FULL | [0.3195, 0.4413, 0.4935, 0.5687] | DORMER-M3-001 | - | PENDING |

Relation review: REL-M3-001 (FC-M3-004, FC-M3-005): Vormen de rode balkondeur (004) en het witte raam (005) een onafgebroken raam-deurcombinatie (een opening) of twee openingen? Op de foto loopt een doorlopende witte kozijnbovenregel over beide en ligt er geen metselwerk tussen; de kozijnstijl alleen is geen scheiding. Niet samengevoegd; de mens beslist.

Overlay: `reports/frames/photo_review_rear_v1/maldenhof_3_frame_overlay.png`
