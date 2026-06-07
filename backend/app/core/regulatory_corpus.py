"""
Seed corpus of real regulatory events with dates.
Sources: EUR-Lex, UK legislation, US Federal Register, Wikipedia.

This is the foundation of the real causal graph.
Each event has a date, description, jurisdiction, and category.
When a document changes near one of these dates, ChronoLens
can cite the event as a potential causal factor.
"""

REGULATORY_EVENTS = [
    # ── GDPR & EU Privacy ──────────────────────────────────────────
    {
        "event_date": "2018-05-25",
        "title": "GDPR Enforcement Begins",
        "description": "The EU General Data Protection Regulation (GDPR) became enforceable. Organizations must comply with data subject rights, breach notification (72h), DPO requirements, and privacy by design.",
        "source_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32016R0679",
        "jurisdiction": "EU",
        "category": "privacy",
    },
    {
        "event_date": "2020-07-16",
        "title": "Schrems II — EU-US Privacy Shield Invalidated",
        "description": "Court of Justice of EU invalidated EU-US Privacy Shield in Data Protection Commissioner v Facebook Ireland. Organizations must use Standard Contractual Clauses with supplementary measures for US data transfers.",
        "source_url": "https://curia.europa.eu/juris/document/document.jsf?docid=228677",
        "jurisdiction": "EU",
        "category": "privacy",
    },
    {
        "event_date": "2021-06-28",
        "title": "EU Adequacy Decision for UK",
        "description": "European Commission adopted adequacy decisions for the United Kingdom under GDPR and LED, allowing personal data to flow freely from EU to UK.",
        "source_url": "https://commission.europa.eu/law/law-topic/data-protection_en",
        "jurisdiction": "EU",
        "category": "privacy",
    },
    {
        "event_date": "2023-07-10",
        "title": "EU-US Data Privacy Framework Adopted",
        "description": "European Commission adopted adequacy decision for EU-US Data Privacy Framework, replacing the invalidated Privacy Shield and enabling transatlantic data flows.",
        "source_url": "https://commission.europa.eu/document/fa09cbad-dd7d-4684-ae60-be03fcb0fddf_en",
        "jurisdiction": "EU",
        "category": "privacy",
    },

    # ── EU Digital Markets & AI ────────────────────────────────────
    {
        "event_date": "2022-10-01",
        "title": "EU Digital Services Act Enters into Force",
        "description": "DSA entered into force establishing obligations for online platforms: content moderation, algorithmic transparency, targeted advertising restrictions for minors.",
        "source_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32022R2065",
        "jurisdiction": "EU",
        "category": "digital_markets",
    },
    {
        "event_date": "2023-05-02",
        "title": "EU Digital Markets Act Enforcement Begins",
        "description": "DMA became enforceable. Designated gatekeepers (Apple, Google, Meta, Amazon, Microsoft, ByteDance) must comply with interoperability, data portability, and fair access obligations.",
        "source_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32022R1925",
        "jurisdiction": "EU",
        "category": "digital_markets",
    },
    {
        "event_date": "2024-08-01",
        "title": "EU AI Act Enters into Force",
        "description": "The EU Artificial Intelligence Act entered into force — the world's first comprehensive AI regulation. Establishes risk-based framework: unacceptable risk (banned), high risk (conformity assessment), limited risk (transparency obligations).",
        "source_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32024R1689",
        "jurisdiction": "EU",
        "category": "ai_regulation",
    },
    {
        "event_date": "2025-02-02",
        "title": "EU AI Act — Prohibited AI Systems Ban Takes Effect",
        "description": "First phase of EU AI Act enforcement: banned AI systems including social scoring, real-time biometric surveillance, and subliminal manipulation techniques become illegal.",
        "source_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32024R1689",
        "jurisdiction": "EU",
        "category": "ai_regulation",
    },
    {
        "event_date": "2025-08-02",
        "title": "EU AI Act — GPAI Model Obligations Take Effect",
        "description": "General Purpose AI model providers must comply with transparency, copyright, and systemic risk assessment obligations under EU AI Act.",
        "source_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32024R1689",
        "jurisdiction": "EU",
        "category": "ai_regulation",
    },

    # ── Financial & Crypto ─────────────────────────────────────────
    {
        "event_date": "2023-06-09",
        "title": "EU MiCA Regulation Adopted",
        "description": "Markets in Crypto-Assets (MiCA) regulation adopted by European Parliament — comprehensive framework for crypto-asset service providers, stablecoin issuers, and asset-referenced tokens.",
        "source_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32023R1114",
        "jurisdiction": "EU",
        "category": "crypto_finance",
    },
    {
        "event_date": "2024-06-30",
        "title": "EU MiCA Stablecoin Rules Effective",
        "description": "MiCA provisions for asset-referenced tokens and e-money tokens became applicable. Stablecoin issuers must obtain authorization and maintain adequate reserves.",
        "source_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32023R1114",
        "jurisdiction": "EU",
        "category": "crypto_finance",
    },
    {
        "event_date": "2024-12-30",
        "title": "EU MiCA Full Application",
        "description": "Full MiCA regulation applies to all crypto-asset service providers. Exchanges, custodians, and trading platforms must be authorized under MiCA.",
        "source_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32023R1114",
        "jurisdiction": "EU",
        "category": "crypto_finance",
    },
    {
        "event_date": "2021-09-07",
        "title": "El Salvador Adopts Bitcoin as Legal Tender",
        "description": "El Salvador became first country to adopt Bitcoin as legal tender under Bitcoin Law, requiring all businesses to accept BTC payments.",
        "source_url": "https://www.bcr.gob.sv/bcrsite/uploaded/content/category/1109762141.pdf",
        "jurisdiction": "SV",
        "category": "crypto_finance",
    },
    {
        "event_date": "2022-11-11",
        "title": "FTX Collapse and Bankruptcy",
        "description": "FTX cryptocurrency exchange filed for Chapter 11 bankruptcy. Sam Bankman-Fried arrested. $8 billion in customer funds missing. Triggered global crypto regulatory responses.",
        "source_url": "https://cases.ra.kroll.com/FTX/",
        "jurisdiction": "US",
        "category": "crypto_finance",
    },
    {
        "event_date": "2024-01-10",
        "title": "SEC Approves Bitcoin Spot ETFs",
        "description": "US SEC approved 11 Bitcoin spot ETFs including BlackRock iShares Bitcoin Trust, enabling institutional investors to access Bitcoin through regulated exchange-traded products.",
        "source_url": "https://www.sec.gov/cgi-bin/browse-edgar",
        "jurisdiction": "US",
        "category": "crypto_finance",
    },

    # ── Climate & ESG ──────────────────────────────────────────────
    {
        "event_date": "2021-07-14",
        "title": "EU Fit for 55 Package Published",
        "description": "European Commission published Fit for 55 legislative package — 13 proposals to reduce EU greenhouse gas emissions 55% by 2030. Includes revised ETS, carbon border adjustment, renewable energy targets.",
        "source_url": "https://www.consilium.europa.eu/en/policies/green-deal/fit-for-55-the-eu-plan-for-a-green-transition/",
        "jurisdiction": "EU",
        "category": "climate",
    },
    {
        "event_date": "2023-01-01",
        "title": "EU Corporate Sustainability Reporting Directive Applies",
        "description": "CSRD entered application for large public-interest companies — mandatory sustainability reporting with ESRS standards, third-party assurance requirements.",
        "source_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32022L2464",
        "jurisdiction": "EU",
        "category": "climate",
    },
    {
        "event_date": "2024-03-06",
        "title": "SEC Climate Disclosure Rules Adopted",
        "description": "US SEC adopted final rules requiring public companies to disclose material climate risks, Scope 1 and 2 GHG emissions, and climate-related targets.",
        "source_url": "https://www.sec.gov/rules/final/2024/33-11275.pdf",
        "jurisdiction": "US",
        "category": "climate",
    },

    # ── Cybersecurity ──────────────────────────────────────────────
    {
        "event_date": "2023-01-16",
        "title": "EU NIS2 Directive Enters into Force",
        "description": "Network and Information Security Directive 2 entered into force — expands cybersecurity obligations to more sectors, stricter incident reporting (24h initial, 72h detailed), supply chain security requirements.",
        "source_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32022L2555",
        "jurisdiction": "EU",
        "category": "cybersecurity",
    },
    {
        "event_date": "2024-10-17",
        "title": "EU NIS2 Transposition Deadline",
        "description": "Member States deadline to transpose NIS2 into national law. Organizations in critical sectors must implement security measures and incident reporting procedures.",
        "source_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32022L2555",
        "jurisdiction": "EU",
        "category": "cybersecurity",
    },
    {
        "event_date": "2025-01-17",
        "title": "EU DORA Digital Resilience Regulation Applies",
        "description": "Digital Operational Resilience Act became applicable for financial sector. Banks, insurers, investment firms must comply with ICT risk management, incident reporting, third-party risk frameworks.",
        "source_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32022R2554",
        "jurisdiction": "EU",
        "category": "cybersecurity",
    },

    # ── US Legislation ─────────────────────────────────────────────
    {
        "event_date": "2020-01-01",
        "title": "CCPA California Consumer Privacy Act Effective",
        "description": "California Consumer Privacy Act became effective — right to know, right to delete, right to opt-out of sale of personal information for California residents.",
        "source_url": "https://oag.ca.gov/privacy/ccpa",
        "jurisdiction": "US",
        "category": "privacy",
    },
    {
        "event_date": "2023-03-02",
        "title": "US National Cybersecurity Strategy Published",
        "description": "Biden Administration published National Cybersecurity Strategy — rebalancing cyber defense responsibility toward technology providers, expanding minimum security standards for critical infrastructure.",
        "source_url": "https://www.whitehouse.gov/wp-content/uploads/2023/03/National-Cybersecurity-Strategy-2023.pdf",
        "jurisdiction": "US",
        "category": "cybersecurity",
    },
    {
        "event_date": "2023-10-30",
        "title": "US Executive Order on AI Safety",
        "description": "President Biden signed Executive Order on Safe, Secure, and Trustworthy Artificial Intelligence — requiring safety testing for frontier AI models, watermarking AI content, protecting privacy.",
        "source_url": "https://www.whitehouse.gov/briefing-room/presidential-actions/2023/10/30/executive-order-on-the-safe-secure-and-trustworthy-development-and-use-of-artificial-intelligence/",
        "jurisdiction": "US",
        "category": "ai_regulation",
    },
]