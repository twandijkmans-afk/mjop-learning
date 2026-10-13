"""MJOP Photo Reviewer - offline Proof of Concept (docs/photo_reviewer_poc_v1.md).

Verwerkt foto-voorstellen (PROPOSED) tot een geverifieerde voorstelset en een apart hoeveelhedencontract.
Dit pakket schrijft nooit (de CLI in scripts/photo_reviewer_demo.py schrijft uitsluitend buiten de repository),
heeft geen netwerkcode op moduleniveau en doet geen externe visionaanroep: de Claude-adapter is standaard
uitgeschakeld en vereist een expliciet toestemmings- en privacyrecord.
"""
