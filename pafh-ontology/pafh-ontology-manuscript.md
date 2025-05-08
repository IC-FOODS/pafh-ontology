# Manuscript: Provenance-Aware Physical Activity, Fitness, and Health Ontology (PAFH)

## Abstract
*To be completed: Brief summary of the ontology, its provenance-aware structure, and its significance for research and practice.*

## Introduction
*To be completed: Motivation for a provenance-aware ontology in health and fitness; gaps in current ontologies; importance of evidence-backed, context-specific assertions.*

While several OBO Foundry ontologies—such as the Ontology for Biomedical Investigations (OBI)—cover aspects of biomedical protocols, measurements, and include some physical activity concepts (e.g., “exercise,” “aerobic exercise”), none provide a detailed, domain-specific hierarchy of physical activity types, measurement methods, or provenance-aware assertions focused on fitness and health outcomes. Other ontologies like ERO (Eagle-i Research Resource Ontology) include research resources and equipment but are not focused on physical activity or fitness. Clinical terminologies such as SNOMED CT and LOINC (not OBO Foundry) include clinical terms for exercise and fitness, but are not open, provenance-aware, or structured for research annotation. MeSH (not OBO Foundry) provides general terms but lacks provenance and detailed relationships.

### Comparison to Similar Ontologies in BioPortal

Several ontologies in BioPortal address exercise, fitness, or health-related concepts, but none provide the comprehensive, provenance-aware, and research-focused modeling found in PAFH. Key comparisons include:

- **SNOMED CT:** Comprehensive clinical terminology with terms for exercise and fitness assessments, but not open access and not designed for detailed research annotation or provenance.
- **LOINC:** Focuses on codes for clinical measurements and exercise testing, but does not model relationships, provenance, or activity hierarchies.
- **MeSH:** Provides general terms for exercise and fitness for literature indexing, but lacks detailed structure, provenance, and extensibility.
- **HPO:** Captures phenotypes related to exercise intolerance or abnormal activity, but does not model physical activity or fitness as primary entities.
- **OAE:** Models exercise as context for adverse events, not as a primary domain.
- **OBI/EFO:** Include some experimental and variable terms related to physical activity, but lack detailed, domain-specific hierarchy and provenance-aware modeling.

| Ontology   | Physical Activity Types | Fitness/Health Focus | Measurement Methods | Provenance/Outcomes | Micro-Location/Context | Open/Extensible |
|------------|------------------------|----------------------|---------------------|---------------------|-----------------------|-----------------|
| **PAFH**   | Detailed, hierarchical | Central              | Yes                 | Yes                 | Yes                   | Yes             |
| SNOMED CT  | Moderate (clinical)    | Moderate             | Yes                 | No                  | Limited               | No              |
| LOINC      | Minimal (codes)        | Measurement only     | Yes                 | No                  | No                    | Yes             |
| MeSH       | General terms          | General              | No                  | No                  | No                    | No              |
| HPO        | Indirect (phenotypes)  | Indirect             | No                  | No                  | No                    | Yes             |
| OAE        | Context only           | Adverse events       | No                  | No                  | No                    | Yes             |
| OBI/EFO    | Minimal                | Experimental         | Some                | No                  | No                    | Yes             |

**Conclusion:**
PAFH is unique among BioPortal ontologies in its comprehensive, provenance-aware, and research-focused modeling of physical activity, fitness, and health. It provides a level of detail, extensibility, and contextual modeling (including micro-locations and measurement methods) not found in other ontologies, which are either clinical, bibliographic, or focused on related but distinct domains.

What makes PAFH unique is its provenance-aware named graph assertions (TriG format) for evidence-backed relationships, a detailed and extensible hierarchy for physical activity, exercise types, measurement methods, and outcomes, and explicit support for linking activities, methods, outcomes, settings, agents, and moderators with provenance. Designed for interoperability, PAFH is focused on the physical activity, fitness, and health research domain and fills a unique gap—especially in supporting evidence-backed, context-specific assertions for physical activity and health research.

This project was guided by several key aims:

1. **Survey the Landscape:** Conduct a thorough review of existing vocabularies and ontologies related to physical activity terminology.
2. **Develop a Unified Model:** Synthesize findings into a comprehensive knowledge model (PAFH-KM) that serves as a foundation for constructing ontologies in the domains of physical activity, fitness, and health.
3. **Enable Practical Application:** Illustrate how these ontologies can be used to annotate data from wearable devices and health records, thereby improving interoperability across diverse systems.
4. **Enhance Public Health Utility:** Increase the level of detail available for population health monitoring and targeted public health interventions.

These objectives provided the framework for the design and implementation of the provenance-aware PAFH ontology described in this manuscript.

## Methods
### Provenance of Ontology Development
- The ontology was developed as a collaborative process initiated by the principal investigator, who provided an initial manuscript draft and a detailed knowledge model describing the resources, relationships, and concepts of interest in the physical activity, fitness, and health domain.
- The ontology engineer (AI assistant) generated the ontology content and structure based on the knowledge model and the manuscript’s description of resources, iteratively refining the ontology in consultation with the principal investigator.
- Key design decisions, such as the use of provenance-aware named graphs and evidence-backed assertions, were made to ensure that each relationship in the ontology is transparent, citable, and extensible.

### Iterative Ontology Development Process
The development of the PAFH ontology followed a structured, iterative approach, progressively increasing the complexity and coverage of the ontology across specific branches. The key steps and order of operations were as follows:

1. **Initial Core Branches and Classes**
   - Began by defining the foundational classes for physical activity, fitness, and health, anchoring them to BFO upper-level classes (e.g., bfo:Process, bfo:Quality).
   - Established the main branches (PhysicalActivity, ActivityType, ObjectiveMeasure, SubjectiveMeasure, PhysicalActivityIntensity) and their initial subclass hierarchies.

2. **Mapping to OBO Foundry and External Ontologies**
   - Added cross-references and equivalence axioms to OBO Foundry ontologies (OBI, RO, IAO) and external resources using skos:exactMatch and owl:equivalentClass.
   - Ensured all core classes had clear, IAO-compliant textual definitions and provenance annotations (dcterms:source).

3. **Expansion of Measurement and Intensity Branches**
   - Developed detailed branches for measurement methods, both objective and subjective, including subclasses for perceived and self-reported intensity, difficulty, fatigue, and duration.
   - Introduced additional subclasses and relationships reflecting domain-specific nuances.

4. **Introduction of Provenance-Aware Named Graphs**
   - Converted all major relationship types (e.g., method-to-outcome, activity-to-outcome, activity-to-purpose, activity-to-setting, activity-to-agent, activity-to-moderator) to a named graph structure using TriG syntax.
   - Annotated each assertion with dcterms:source to provide evidence and support provenance tracking.
   - Removed previous direct triple blocks in favor of the new named graph pattern.

5. **Addition of Logical Axioms and Property Characteristics**
   - Incorporated logical axioms (equivalence, disjointness) and property characteristics (functional, transitive, symmetric, inverse) to enhance reasoning support and OBO Foundry compliance.
   - Documented the rationale and placement of each axiom or property characteristic in the ontology.

6. **Ontology Metadata and Documentation Enhancements**
   - Added comprehensive ontology-level metadata (title, description, creator, publisher, license, versioning, etc.).
   - Included explicit OBO-style ID policy and compliance notes at the top of the ontology file.

7. **Iterative Refinement and Review**
   - Regularly reviewed the ontology in Protégé and with the principal investigator, refining branches, definitions, and relationships based on feedback and emerging requirements.
   - Ensured consistency, extensibility, and readiness for academic dissemination and OBO Foundry registration.

### Ontology Design Decisions
- The PAFH ontology was developed using a provenance-aware, evidence-backed approach to link measurement methods, physical activities, and health outcomes.
- All major relationship types are represented using RDF named graphs (TriG syntax), supporting context-specific, citable, and extensible assertions.
- The ontology structure is designed for extensibility, allowing additional relationships, activities, outcomes, or contextual factors to be added as needed.

**To-Do: Automation of Assertion Expansion**
To further enhance scalability and consistency, a planned future step is to automate the expansion of provenance-backed named graph assertions for all relevant activities, outcomes, and other relationship types in the ontology. This will ensure comprehensive coverage and minimize manual effort.

### Additional Design Considerations
- The ontology reuses terms from OBO Foundry ontologies (OBI, RO, etc.) for maximum interoperability.
- New properties are minted only when existing terms are insufficient.
- The ontology is maintained in Turtle/TriG format for readability and compatibility with standard tools (e.g., Protégé).

## Results

### Ontology Content and Coverage
- The ontology implements all major relationship types (method-to-outcome, activity-to-outcome, activity-to-purpose, activity-to-setting, activity-to-agent, activity-to-moderator) as provenance-aware named graphs.
- Each named graph contains a single relationship triple (e.g., `pafh:Walking pafh:hasOutcome pafh:CardiovascularHealth`) and is annotated with a `dcterms:source` property referencing authoritative evidence (CDC, ACSM, WHO, PubMed IDs, etc.).
- Previous direct triple blocks were removed in favor of the named graph pattern, improving clarity and enabling per-assertion provenance.
- The ontology encodes method-outcome relationships (e.g., `pafh:MetabolicCartMethod pafh:hasMeasurementOutcome pafh:VO2Max`) and activity-outcome relationships (e.g., `pafh:Walking pafh:hasOutcome pafh:CardiovascularHealth`) in named graphs.
- The pattern is applied consistently across all major relationship types, enabling advanced SPARQL queries and automated provenance tracking.

### Example Queries and Use Cases
*To be completed: Add example SPARQL queries and use cases demonstrating how the ontology enables provenance-aware, evidence-backed research and application.*

## Discussion

### Future Directions
The current ontology includes a core set of exercise types and evidence-based linkages to outcomes. However, these can be further expanded in future work to include additional exercise modalities, more granular subtypes, and new evidence-based assertions as the literature evolves. This extensibility will ensure that the ontology remains current and maximally useful for both research and applied settings.

### Future Directions
A key area for future development is the automation of provenance-aware assertion generation. By programmatically expanding named graphs for all valid combinations of activities, outcomes, and other relationships, the ontology can achieve greater coverage, consistency, and ease of maintenance as new terms and evidence sources are added.

*To be completed: Implications, limitations, and additional future directions.*

## References
*To be completed: List of all sources cited (CDC, ACSM, WHO, PubMed IDs, etc.).*
