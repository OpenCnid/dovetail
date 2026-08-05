# Body of Knowledge — the Figure of the Earth

**Compiled July 20, 2026** by three independent sub-agent compilers with
disjoint scopes (geodetic/physical, astronomical, operational/engineering).
**None was told that any dispute over the subject exists** — the framing was
neutral ("what is reliably known and how it is known"), deliberately, so that
facts were not selected to refute a position the compilers knew about.

Each item records: what a source **states**, the **source**, the **kind** of
claim (direct measurement / derived quantity / convention / specification),
whether it is **first-person checkable** by a private individual, and the
**limits** the source itself attaches.

The first-person-checkable field is load-bearing: it separates what an
individual can verify unaided from what rests on institutional attestation.

---

## I. GEODETIC AND PHYSICAL MEASUREMENT

### WGS 84 reference ellipsoid — defining constants
- **States:** a = 6 378 137.0 m; 1/f = 298.257223563; GM = 3.986004418×10^14 m³s⁻²; ω = 7.292115×10⁻⁵ rad s⁻¹. Derived b = 6 356 752.3142 m. Equatorial exceeds polar radius by **~21 384.7 m (21.4 km)**.
- **Source:** NGA.STND.0036_1.0.0_WGS84, v1.0.0, 2014 (superseding NIMA TR8350.2).
- **Kind:** Convention (adopted defining constants); b derived.
- **First-person checkable:** No. The internal arithmetic (b = a(1−f), e² = 2f−f²) is checkable with a calculator.
- **Limits:** a and 1/f are **defined, not measured** — they carry no uncertainty by construction. Frame realizations (G730…G2139) shifted at cm level while constants stayed fixed. The ellipsoid is a best-fitting surface, **not the physical surface**.

### GRS 80 — geometric consequences
- **States:** a = 6 378 137 m, GM = 3 986 005×10^8 m³s⁻², J₂ = 108 263×10⁻⁸, ω = 7 292 115×10⁻¹¹ s⁻¹. Derived: b = 6 356 752.3141 m; 1/f = 298.257222101; meridian quadrant = 10 001 965.729 m; mean radius R₁ = 6 371 008.7714 m; authalic R₂ = 6 371 007.1810 m; volumetric R₃ = 6 371 000.7900 m.
- **Source:** Moritz, H., "Geodetic Reference System 1980," *J. Geodesy* 74 (2000) 128–133, doi:10.1007/s001900050278.
- **Kind:** Convention plus derived quantities.
- **First-person checkable:** Not the constants; the relations between them are computable by anyone.
- **Limits:** GRS 80 derives flattening from J₂; WGS 84 adopts it directly — hence 298.257222101 vs 298.257223563 (~0.1 mm in b). **Which is "the" flattening is convention-dependent.** The quadrant exceeding 10 000 000 m by ~1 966 m records the error in the 18th-century arcs that defined the metre.

### IERS Conventions (2010) — best estimates vs adopted conventions
- **States:** GM = 3.986004418×10^14 ± 8×10⁵; a_E = 6 378 136.6 ± 0.1 m; 1/f = 298.25642 ± 0.00001; J₂ = 1.0826359×10⁻³ ± 1×10⁻¹⁰. Zero-tide values.
- **Source:** Petit & Luzum (eds.), *IERS Conventions (2010)*, IERS TN 36, ch.1 §1.2 Table 1.1.
- **Kind:** Derived quantities / best estimates with uncertainties.
- **First-person checkable:** No.
- **Limits:** **These disagree with WGS 84 and GRS 80 by more than their stated uncertainties** — a_E 6 378 136.6 ± 0.1 m vs 6 378 137 adopted; 1/f 298.25642 vs 298.2572. The disagreement is the permanent-tide convention plus measured-estimate vs adopted-constant. Recorded, not resolved.

### Meridian arc measurement — poleward lengthening of a degree
- **States:** Struve Geodetic Arc (1816–1855): 258 main triangles, 265 station points, ~2 820 km, Hammerfest to the Black Sea across ten modern countries. On WGS 84, one degree of latitude runs from ~110.574 km at the equator to ~111.694 km at the poles.
- **Source:** UNESCO WHC ref. 1187; degree lengths per USGS and NOAA Ocean Service.
- **Kind:** Direct measurement (the campaign); derived quantity (degree lengths).
- **First-person checkable:** Partly. Short-arc baseline/angle work is within reach of a total station or GNSS receiver; detecting the ~1.1 km spread needs a network spanning thousands of km — cooperation, not equipment.
- **Limits:** The degree figures are **computed from the adopted ellipsoid, not measured independently**. Struve-era arcs carried systematic error from unmodelled deflections of the vertical.

### Newton's derivation of oblateness from rotation
- **States:** *Principia* (1687) III Prop. XIX: a homogeneous rotating self-gravitating Earth in equilibrium must be oblate, with f = 1/230.
- **Source:** Newton, *Principia*, 1687, Bk III Prop. XIX Prob. III.
- **Kind:** Derived quantity (theoretical prediction).
- **First-person checkable:** No — but the prediction's *direction* (equatorial, not polar, bulge) is what 18th-century arc measurement tested.
- **Limits:** 1/230 assumes uniform density. The real Earth is centrally condensed, giving ~1/300. **Right mechanism, wrong density model** — not to be quoted as a failed prediction.

### Earth is measurably more flattened than hydrostatic equilibrium allows
- **States:** Observed equator-to-pole radius difference exceeds the hydrostatic value by **113 ± 1 m** (revised up from 98 m).
- **Source:** Chambat, Ricard & Valette, "Flattening of the Earth: further from hydrostaticity than previously estimated," *GJI* 183 (2010) 727–732, doi:10.1111/j.1365-246X.2010.04771.x.
- **Kind:** Derived quantity (observation minus equilibrium theory).
- **First-person checkable:** No.
- **Limits:** Depends on the adopted radial density model (PREM-class) and inertia ratio — model-dependent at the level of the correction itself, which is why 98 m became 113 m. Observed J₂ must first be corrected for atmospheric mass and permanent tide. The excess is ~0.5% of the 21.4 km total.

### Size threshold above which self-gravity makes a body round
- **States:** Bodies become hydrostatic-equilibrium spheres above roughly 200 km radius (icy) / 300 km (rocky). Below, material strength supports irregular shapes.
- **Source:** Lineweaver & Norman, "The Potato Radius," arXiv:1004.1091 (2010).
- **Kind:** Derived quantity (first-principles order-of-magnitude).
- **First-person checkable:** No.
- **Limits:** Explicitly order-of-magnitude; depends on assumed yield strength and density; a range, not a sharp threshold. Earth exceeds it by >1 order of magnitude.

### Normal gravity varies systematically with latitude
- **States:** Somigliana equation on WGS 84: γ_e = 9.7803253359 m s⁻² (equator), γ_p = 9.8321849378 m s⁻² (pole). Equator-to-pole increase 0.0518596 m s⁻², **~0.53%**.
- **Source:** NGA.STND.0036_1.0.0_WGS84 (2014) §4.
- **Kind:** Derived quantity from an adopted convention — **not a direct measurement**.
- **First-person checkable:** Marginally. 0.53% is at the edge of careful pendulum/spring work and needs wide latitude travel. Historically noticed via a pendulum clock losing time near the equator.
- **Limits:** Gravity of a *model* ellipsoid. Real measured gravity departs by anomalies of order 10⁻⁴ m s⁻². Free-air gradient ~0.3086 mGal m⁻¹, Bouguer ~0.1967 mGal m⁻¹ (Hofmann-Wellenhof & Moritz, *Physical Geodesy*, 2006). **Latitude and elevation effects are comparable in size and inseparable without knowing both.**

### Measured extremes of surface gravity
- **States:** Minimum 9.7639 m s⁻² at Nevado Huascarán summit, Peru; maximum 9.8337 m s⁻² at the Arctic Ocean surface. Spread ~0.07 m s⁻² (~0.7%).
- **Source:** Hirt et al., "New ultrahigh-resolution picture of Earth's gravity field," *GRL* 40 (2013) 4279–4283, doi:10.1002/grl.50838.
- **Kind:** Derived quantity (GGMplus model outputs), **not point measurements**.
- **First-person checkable:** No, not at this precision without a gravimeter.
- **Limits:** Model coverage stops at ±60° latitude, excluding higher-latitude land from the extremes search. **The Huascarán minimum is 1 000 km from the equator** — elevation and local anomalies there outweigh the latitude term, so this is *not* a clean demonstration of the latitude effect.

### Metrological limit of absolute gravity measurement
- **States:** CIPM key comparison CCM.G-K2.2023 (Boulder, Aug–Sep 2023): 30 absolute gravimeters, 27 institutes, 15 NMIs. Standard deviation of degrees of equivalence **< 1.3 µGal** (1 µGal = 10⁻⁸ m s⁻²). No participant excluded.
- **Source:** *Metrologia* 61 (2024) Tech. Suppl. 07009, doi:10.1088/0026-1394/61/1A/07009.
- **Kind:** Direct measurement (free-fall and atom interferometry).
- **First-person checkable:** No — laboratory instruments costing ~$10⁵.
- **Limits:** 1.3 µGal is **agreement between instruments** (~1.3 parts in 10⁹ of g), not the accuracy of any field measurement. Degrees of equivalence are relative to a comparison reference value, not an independent absolute standard.

### The geoid departs from the ellipsoid by tens of metres
- **States:** EGM2008, complete to degree 2159. Geoid heights (geoid minus WGS 84 ellipsoid) range **−106 m to +85 m**. Where good terrestrial gravity exists, EGM2008 vs GPS/levelling agrees to ±5–10 cm.
- **Source:** Pavlis et al., *JGR Solid Earth* 117 (2012) B04406, doi:10.1029/2011JB008916.
- **Kind:** Derived quantity (model constrained by satellite, terrestrial, airborne, altimetric data).
- **First-person checkable:** Not the global range. **Locally yes:** a GNSS receiver reports ellipsoidal height, a spirit-levelled benchmark reports orthometric height, and their difference reproduces the local undulation to a few cm.
- **Limits:** The range is a property of the distributed grid, shifting between releases and tide systems. ±5–10 cm applies only to well-surveyed regions. **Quoting a geoid height without naming ellipsoid and tide system is ambiguous.**

### Terrestrial curvature measured over line-of-sight distances
- **States:** Standard surveying applies a combined curvature-and-refraction correction **h = 0.0675 K²** metres (K in km): ~6.75 cm at 1 km, 1.69 m at 5 km, 6.75 m at 10 km. Refraction opposes curvature at roughly one-seventh its size; coefficient k ≈ 0.13. Independently, Rawlins timed a "double sunset" at Cove Park, La Jolla, 5 April 1978: last ray gone at 6:11:55 pm from 1.72 m elevation, 6:12:15 pm from 8.95 m — a **19.6 s** interval yielding the Earth's radius.
- **Source:** Rawlins, D., *Am. J. Phys.* 47(2) (1979) 126–128; Aravind, *Phys. Educ.* 43 (2008) / arXiv:0812.3911; Torge, *Geodesy* 3rd ed.; Ghilani & Wolf, *Elementary Surveying*.
- **Kind:** Direct measurement.
- **First-person checkable: YES — the most accessible item in this scope.** Double-sunset needs a stopwatch, a measured height difference, and a sea horizon. Long-distance spirit levelling that omits the 0.0675 K² term **fails to close**, which any surveyor can confirm.
- **Limits:** **Atmospheric refraction is the dominant error and is not constant** — k varies with temperature gradient, is largest and most variable over water and in the lowest few metres, and can invert (superior mirage, looming) so distant objects appear far higher than geometry predicts. Single observations under unmeasured refraction are not decisive at short ranges; k ≈ 0.13 is an average. Rawlins' method is latitude- and season-sensitive, with observer reaction error of ~1 s on a ~20 s interval (several % in the derived radius).

### Coverage gaps declared by this compiler
- Direct over-water curvature experiments with published error analysis exist only as self-published write-ups (e.g. Rainy Lake 2018, ~10 km sight lines, reported radius ~6 400 km), not peer-reviewed. Bedford Level (Rowbotham 1838; Wallace's corrected 1870 repetition) is better documented in secondary history than in retrievable primary reports.
- IERS TN36 Table 1.1 and Moritz (2000) primary PDFs could not be extracted (503/429/blocked); values confirmed via search excerpts and cross-checked for consistency.
- Chambat et al.'s tabulated J₂/J₄ values not retrieved — only the headline 113 ± 1 m.
- **Satellite gravimetry (GRACE, GRACE-FO, GOCE) and SLR determinations deliberately left to the operational scope — meaning this compilation understates currently available precision.**
- Levelling-network and tide-gauge evidence not anchored to a primary national-survey report this pass.
- No standards-body table sourced for degree-length-vs-latitude; those figures are **computed, not measured**.

---

## II. ASTRONOMICAL OBSERVATION

### Eratosthenes' measurement
- **States:** Cleomedes reports Eratosthenes (c. 240 BC) found the Alexandria gnomon shadow-arc to be 1/50 of a circle (7.2°) with the Sun overhead at Syene, and Syene–Alexandria = 5 000 stades, giving 250 000 stades. Strabo, Pliny, Vitruvius, Hero and Theon report **252 000** instead.
- **Source:** Cleomedes, *On the Circular Motions* I.7, via MAA Convergence (Walkup).
- **Kind:** Derived quantity from two shadow-angle observations plus an assumed baseline.
- **First-person checkable:** Yes in method — two observers at different latitudes on ~the same meridian, a vertical stick and a protractor, plus an independent distance.
- **Limits:** The 250 000 vs 252 000 discrepancy is **unresolved in the sources**. The baseline came from caravan-route estimates. Syene is neither exactly on Alexandria's meridian nor exactly on the Tropic.

### The stade conversion is convention-dependent
- **States:** No agreed modern equivalent. Proposals run ~500–600 feet, placing the result between ~24 000 and ~29 000 miles. The "common" stade of 185 m gives 46 620 km (**~16% high**); a short "itinerary stade" of ~157.5 m gives ~39 400 km (**within ~2%**). Scholarship is split.
- **Source:** MAA Convergence (Walkup); itinerary-stade dispute in secondary literature.
- **Kind:** Convention, with an unresolved scholarly dispute attached.
- **First-person checkable:** No.
- **Limits:** **The frequently repeated "accurate to 1–2%" claim is contingent on choosing the short stade, which is itself contested. It should not be reported as an established figure.** Full text of the itinerary-stade paper not retrievable (403/521).

### Modern replication of Eratosthenes' method
- **States:** Observers in Australia and New Zealand obtained a best circumference of **38 874 km** (Rosebud, Victoria ↔ Jimboomba, Queensland) — a 2.9% error.
- **Source:** Longhorn & Hughes, *Physics Education* 50(2) 175 (2015), doi:10.1088/0031-9120/50/2/175.
- **Kind:** Direct observation yielding a derived quantity.
- **First-person checkable:** Yes — the paper's explicit purpose, proposed as school-to-school cooperation.
- **Limits:** 2.9% is the **best** pairing, not a mean; no formal error budget in the abstract. Accuracy depends strongly on north–south separation and on catching local solar noon precisely.

### Curvature of Earth's shadow at lunar eclipses
- **States:** Aristotle: in lunar eclipses "the outline is always curved… the form of this line will be caused by the form of the earth's surface, which is therefore spherical." Force of the argument: the edge is curved **regardless** of eclipse location or Moon altitude; a disc would cast an elliptical or straight-edged shadow at some orientations.
- **Source:** Aristotle, *De Caelo* II.14 (297b–298a).
- **Kind:** Direct observation.
- **First-person checkable:** Yes. Any partial lunar eclipse, naked eye or binoculars; photographing several at different Moon altitudes and circle-fitting the terminator is within consumer-camera reach.
- **Limits:** The umbral edge is **diffuse** (extended Sun, Earth's atmosphere), so curvature is only approximately measurable by eye. Establishes a curved cross-section in every observed orientation; **does not by itself yield a radius or distinguish sphere from close spheroid.**

### Size of Earth's umbral shadow at the Moon's distance
- **States:** Umbral diameter at the Moon's distance is typically **~2.7×** the Moon's diameter. Observers have reported for 300+ years that the umbra appears **larger than simple geometry predicts**, attributed to Earth's atmosphere.
- **Source:** Espenak, NASA GSFC eclipse pages; enlargement modelled in Mallama, arXiv:2112.08966.
- **Kind:** Derived quantity from observed geometry.
- **First-person checkable:** Partially — the ratio can be estimated by fitting the umbral arc in a wide-field eclipse photograph; diffuse edge limits precision.
- **Limits:** **Retrieval caveat: both NASA pages failed to fetch (ECONNRESET) and the author's mirror returned 403.** The 2.7× figure is from search-engine extraction, not a page read directly — indicative pending confirmation. Competing enlargement conventions (Danjon vs Chauvenet, ~1–2%) disagree and could not be documented.

### Different stars visible from different latitudes
- **States:** Aristotle: "quite a small change of position to south or north causes a manifest alteration of the horizon"; stars "which in the north are never beyond the range of observation, in those regions rise and set"; "there are some stars seen in Egypt and in the neighbourhood of Cyprus which are not seen in the northerly regions."
- **Source:** Aristotle, *De Caelo* II.14.
- **Kind:** Direct observation.
- **First-person checkable: Yes — among the most accessible items here.** Canopus (δ ≈ −52.7°) is visible from southern Florida but never from the northern US; Polaris is never visible from the southern hemisphere. Needs only travel and a clear horizon.
- **Limits:** Aristotle's further inference (Earth "not large") rests on his claim that contemporary mathematicians computed the circumference at **400 000 stades** — ~60% above the 250 000 later reported. **The ancient figures are mutually inconsistent**; recorded as stated, not reconciled.

### Altitude of the celestial pole equals the observer's latitude
- **States:** The celestial pole stands at an altitude equal to the observer's latitude (worked example: San Francisco 38° N). Stars within that angular distance of the pole never set; within the same distance of the opposite pole, never rise. At the North Pole the pole is at zenith and only half the sky is ever visible; at the equator both poles lie on the horizon and every star is up exactly half of every 24 hours.
- **Source:** Fraknoi, Morrison & Wolff, *Astronomy 2e*, OpenStax, §2.1.
- **Kind:** Derived quantity (geometric relation confirmed by observation).
- **First-person checkable:** Yes. Measure Polaris' altitude with a protractor-and-plumb-line or smartphone inclinometer and compare with latitude; typically agrees within ~1°. Polaris is ~0.7° from the true pole.
- **Limits:** Holds for **astronomical** latitude (local vertical). Geodetic differs by up to ~11 arcmin at mid-latitudes; astronomical vs geodetic differs by the local deflection of the vertical. **This distinction is not stated in the source** and is flagged as unsourced there. Refraction lifts objects near the horizon, biasing low-latitude measurements.

### Stellar parallax — Bessel's 61 Cygni and the modern value
- **States:** Bessel (1838): parallax 0.3136 ± 0.0202 arcsec, announced as 10.4 ly — the first successful trigonometric stellar distance. Modern: 286.005 ± 0.029 mas (Gaia DR3, 61 Cyg A) = 11.40 ± 0.003 ly. Reid & Menten (2020) find von Struve and Henderson "underestimated some of their measurement errors."
- **Source:** Bessel (1838) *AN*; Reid & Menten, *AN* 341(9) 860–869 (2020), doi:10.1002/asna.202013833; Gaia DR3.
- **Kind:** Direct observation yielding a derived quantity.
- **First-person checkable:** No for these stars.
- **Limits:** **Bearing on Earth's shape is indirect** — parallax establishes that the observing platform moves ~2 AU over six months (i.e. Earth orbits) and sets stellar distances; it does not measure Earth's figure. 19th-century parallax uncertainties should not be taken at face value.

### Observed oblateness of other planets
- **States:** IAU values: Jupiter equatorial 71 492 ± 4 km vs mean 69 911 ± 6 km; Saturn equatorial 60 268 ± 4 km vs mean 58 232 ± 6 km. NASA quotes Jupiter ellipticity 0.06487, Saturn oblateness 0.09796. Rapidly rotating fluid bodies are visibly flattened; the same physics predicts far smaller flattening for the slower, rigid Earth.
- **Source:** Archinal et al., *CeMDA* 130, 22 (2018), doi:10.1007/s10569-017-9805-5, as tabulated by JPL SSD.
- **Kind:** Derived quantity (occultation, imaging, spacecraft tracking).
- **First-person checkable:** Partially — Saturn's and Jupiter's flattening is discernible in a modest amateur telescope and measurable from a stacked amateur image.
- **Limits:** Giant-planet radii are defined at a **reference pressure level** (1 bar Jupiter; 100 mbar Saturn per NASA) — **convention-dependent, not physical surfaces** — and the JPL page read does not state which level it uses. The ellipticity figures come from NASA pages that could not be fetched (redirect, no data) and are reported second-hand.

### Roundness as a formal criterion for planethood
- **States:** IAU Resolution B5 (24 Aug 2006): a planet "has sufficient mass for its self-gravity to overcome rigid body forces so that it assumes a hydrostatic equilibrium (nearly round) shape."
- **Source:** IAU 2006 GA Resolution B5.
- **Kind:** Convention.
- **First-person checkable:** No — a definitional act, not a measurement.
- **Limits:** **This is a convention, not observational evidence about the Earth.** "Nearly round" is unquantified, a vagueness noted in later literature. **Direct fetch of the resolution PDF returned 403**; wording is from search against the IAU URL, not a PDF read directly.

### Sunrise and sunset are defined against a refracted horizon
- **States:** USNO defines sunrise/sunset as the upper limb on the horizon under average conditions on level terrain; computationally when the Sun's centre is at zenith distance **90.8333°** — 50 arcmin below horizontal, comprising the Sun's mean apparent radius (16′) plus mean horizon refraction (34′). UT1 is a measure of Earth's rotation angle observed astronomically; civil zones are spaced 15° per hour.
- **Source:** USNO Astronomical Applications, "Rise, Set, and Twilight Definitions"; "Universal Time."
- **Kind:** Convention.
- **First-person checkable:** Yes. Two observers on the same parallel at known longitudes time local apparent noon or sunset; the offset tracks 4 minutes per degree.
- **Limits:** **Conventions, not measurements** — 34′ is an average, and USNO notes accuracy "decreases significantly" at high latitudes. The 15°/hour statement was not found verbatim on the page read. Real civil zones deviate from meridian geometry politically.

### Seasonal daylight at high latitudes
- **States:** At the June solstice all places within 23° of the pole have 24-hour sunshine; each pole gets six months of sun then six of darkness; near the equator the Sun is up ~12 h every day.
- **Source:** Fraknoi, Morrison & Wolff, *Astronomy 2e*, OpenStax, §4.2.
- **Kind:** Direct observation (pattern) explained by a derived geometric model.
- **First-person checkable:** Yes, given travel.
- **Limits:** **The source rounds inconsistently** — states the Arctic Circle as "90° − 23° (or 67° N)" whereas obliquity is 23.44° and the conventional circle is 66.56° N. The idealised six-and-six neglects refraction and solar angular radius, which extend apparent daylight by several days at each end and make polar day measurably longer than polar night; **the source does not mention this.**

### Coverage gaps declared by this compiler
- No primary observational report sourced for circumpolar-star visibility vs latitude; the relation |δ| > 90° − φ appears in lecture notes rather than authoritative sources, so it is given only in the textbook's phrasing.
- **Earth's own oblateness is deliberately absent** (left to the geodetic scope) — with the consequence that this list establishes the Earth is *round* far more strongly than it constrains Earth's *figure*.
- Historically important longitude-by-lunar-eclipse-timing not sourced.
- Three NASA/Espenak pages and the IAU PDF unfetchable (ECONNRESET, 403).
- Moon shapes (in scope) not represented — Archinal et al. paywalled.
- **"Eratosthenes was accurate to 2%" deliberately not resolved** — the most-repeated figure in the domain, entirely contingent on an unsettled unit conversion.

---

## III. OPERATIONAL AND ENGINEERING SYSTEMS

### WGS 84 reference frame agreement with the ITRF
- **States:** "The WGS 84 (G1762) Reference Frame compared to ITRF2008 shows a Root Mean Square (RMS) difference of one centimeter overall." Realization accuracy improved 10 cm/component (1994) → 5 cm (1996) → 1 cm (2002) → <1 cm (2012, 2013).
- **Source:** NGA.STND.0036_1.0.0_WGS84 (2014) §7.2.1 and §2.
- **Kind:** Operational record (two independently maintained frames compared).
- **First-person checkable:** Partially — with a survey-grade GNSS receiver and free IGS/NGA precise ephemerides, an individual can process the same data against both frames and observe cm agreement. Consumer receivers cannot resolve this.
- **Limits:** Realization- and epoch-specific. §7.2.2 notes high-accuracy users must quantify differences for ITRF-based national datums rather than assume identity.

### GPS broadcast-ephemeris user algorithm — ECEF frame and Earth constants
- **States:** ECEF defined with origin at Earth's centre of mass, Z along the IERS Reference Pole, X at the IERS Reference Meridian. Table 20-IV: μ = 3.986005×10^14 m³s⁻²; Ω̇e = 7.2921151467×10⁻⁵ rad s⁻¹. Satellite position solves Kepler's equation then rotates by accumulated Earth rotation. π is pinned to 3.1415926535898 because "the sensitivity of position to the angular parameters is on the order of 10^8 meters/semicircle."
- **Source:** *IS-GPS-200D*, 7 Dec 2004, §20.3.3.4.3.3.1, §20.3.3.4.3.2, Table 20-IV.
- **Kind:** Specification.
- **First-person checkable: Yes, in part.** Download a broadcast ephemeris (RINEX nav file, freely published), implement Table 20-IV, and compare resulting satellite ECEF coordinates against IGS precise ephemerides; metre-level agreement confirms the frame and constants the constellation actually uses. Needs a computer, not special hardware.
- **Limits:** Rev D is superseded. **The GPS user value μ = 3.986005×10^14 differs from the WGS 84 defining GM = 3.986004418×10^14** — the older value is retained for user algorithms; the two sources disagree and neither resolves the other.

### GPS relativistic clock correction
- **States:** Δt_r = F·e·√A·sin E_k, with F = −2√μ/c² = −4.442807633×10⁻¹⁰ s/√m. Control segment uses Δt_r = −(R⃗·V⃗)/c².
- **Source:** *IS-GPS-200D* §20.3.3.3.3.1.
- **Kind:** Specification.
- **First-person checkable:** No, not directly (tens of ns over an orbit). The constant's arithmetic is verifiable.
- **Limits:** Covers the eccentricity-dependent periodic term only; the constant rate offset is absorbed into satellite clock rate at manufacture. States the constant, not an independent measurement of μ.

### GPS SPS — accuracy standard and frame assumption
- **States:** Assumes a receiver computing in "the most current realization of the World Geodetic System 1984 ECEF coordinate system." Global average ≤ 8 m 95% horizontal, ≤ 13 m 95% vertical; worst site ≤ 15 m / ≤ 33 m; velocity ≤ 0.2 m s⁻¹ 95%; time transfer ≤ 30 ns 95%.
- **Source:** DoD, *GPS SPS Performance Standard*, 5th ed., April 2020, §3.8, Table 3.8-3.
- **Kind:** Specification (a committed floor, not a measurement).
- **First-person checkable:** Yes. Log positions at a surveyed benchmark with any consumer receiver and confirm few-metre horizontal error, i.e. that the WGS 84 solution is globally consistent at that scale.
- **Limits:** Commitments about the signal-in-space contribution under stated receiver assumptions and error exclusions; assumes 5° mask angle and nominal noise. Actual accuracy is typically better.

### ICAO adoption of WGS-84 as the common aviation datum
- **States:** ICAO Council approved FANS/4 Rec. 3.2/1 on 3 March 1989 adopting WGS 84 as a standard; Amendment 28 to Annex 15 adopted 28 Feb 1994. Rationale (Doc 9674 §1.1.4): "the main source of systematic errors is the non-use of a common geodetic reference datum for determining radar positions."
- **Source:** EUROCONTROL/IfEN *WGS 84 Implementation Manual* v2.4 (1998), Foreword; ICAO Doc 9674 (2002) §§1.1.4–1.1.6, 1.4.1.
- **Kind:** Specification / regulatory record.
- **First-person checkable:** Partially — published AIP coordinates are labelled WGS-84 and freely readable; an airport reference point checks against a handheld receiver to metres-to-tens-of-metres.
- **Limits:** Doc 9674 consulted as a purchase preview (§§1.1–1.4 only). §1.1.6 notes the datum requirement does not significantly affect VOR/NDB radial navigation en route — it bites for area navigation, radar and surveying. Annex texts are paywalled and were not read.

### ICAO PBN — flight paths computed as geodesics
- **States:** "Geodesic or great circle paths joining the flight plan waypoints… are calculated by the RNAV or RNP system." Direct-to must generate "a geodesic path to the designated 'To' fix."
- **Source:** ICAO Doc 9613, 5th ed. (2023), Vol I §3.5; Vol II Part C; §1.3.3.7.
- **Kind:** Specification.
- **First-person checkable:** Partially. **A passenger can log an aircraft's position with a handheld GNSS receiver over a long flight and confirm the track is a geodesic arc rather than a straight line on a Mercator chart** — the two diverge by hundreds of km transoceanic. Requires plotting on a projection whose properties the individual understands.
- **Limits:** The manual does not prescribe which ellipsoid computation (e.g. Vincenty) nor bound the geodesic-vs-great-circle difference. Flown routes deviate for airspace, wind and ETOPS reasons; the spec governs path *definition* between waypoints, not route selection.

### ITU-R effective Earth radius (k-factor)
- **States:** A transformation to "a hypothetical Earth of effective radius Re = k a" makes ray trajectories linear. "For heights below 1 000 m… The corresponding k-factor is **k = 4/3**." Refractive modulus M = N + h/a.
- **Source:** ITU-R Rec. P.834-9, Dec 2017, Annex 1 §2, §3.
- **Kind:** Specification.
- **First-person checkable: Yes, in effect.** An amateur radio operator can observe that reliable line-of-sight range over open water or flat terrain extends measurably beyond the geometric horizon of an unrefracted sphere, and scales as √(antenna height). Quantitative agreement with k = 4/3 requires careful measurement.
- **Limits:** k = 4/3 is an **average** for heights below 1 000 m and depends on the refractivity gradient, which varies with weather; ducting and non-standard gradients are handled elsewhere in the same document. Exact only for a constant gradient and near-horizontal paths.

### ITU-R diffraction over a spherical Earth
- **States:** "If no other information is available, an equivalent Earth radius of **8 500 km** may be taken as a basis." Additional loss from diffraction over a spherical Earth computed by the classical residue series; step-by-step procedure for any path length at ≥10 MHz.
- **Source:** ITU-R Rec. P.526-13, Nov 2013, Annex 1 §1, §3, §3.2.
- **Kind:** Specification.
- **First-person checkable:** Yes, in part. An individual can observe that a distant transmitter's signal falls off sharply beyond the horizon distance predicted for an ~8 500 km effective radius, as a smooth diffraction decay rather than an abrupt cutoff.
- **Limits:** 8 500 km is a **default**, dependent on the actual refractivity gradient. Methods stated for ≥10 MHz. Over-the-horizon first-term approximation carries up to ~2 dB error near the horizon. Superseded by later revisions.

### Geostationary orbit — altitude and sidereal period
- **States:** GEO satellites match Earth's rotation, taking 23 h 56 min 4 s (one sidereal day), travelling ~3 km s⁻¹ at **35 786 km** altitude. NASA concurs on the altitude.
- **Source:** ESA, *Types of orbits*; NASA Earthdata, *Orbits*.
- **Kind:** Derived quantity (radius follows from GM and sidereal period via Kepler's third law).
- **First-person checkable: Yes.** A fixed, non-tracking satellite dish confirms a GEO satellite stays in a fixed direction indefinitely; the dish elevation angle at known latitude varies as a 42 164 km orbital radius above a ~6 371 km Earth predicts, dropping to zero near ±81°.
- **Limits:** ESA's page is public-outreach material, not a technical standard; figures rounded and the exact radius depends on the adopted GM. Real satellites are held in a station-keeping box, not exactly stationary.

### Sun-synchronous orbit — dependence on Earth's oblateness (J2)
- **States:** Ω̇ = −(3 R_E² J₂ √μ_E)/(2 a^(7/2)(1−e²)²)·cos(i), with J₂ = 1.08263×10⁻³. Sun-synchrony requires Ω̇ = 360°/365.2422 d = 0.9856 °/day = 2×10⁻⁷ rad s⁻¹.
- **Source:** Paek, Kim, Kronig & de Weck, ISSFD 2019, Eq. (1).
- **Kind:** Derived quantity (first-order secular J2 perturbation), in peer-reviewed literature.
- **First-person checkable:** Partially. Over months an individual can observe (via published TLEs, naked eye or binoculars) that a Sun-synchronous platform passes overhead at the same local solar time. **Confirming J₂ specifically is the cause requires the derivation, not observation alone.**
- **Limits:** Conference paper, rounded constants. First-order secular approximation neglecting higher zonals, drag, luni-solar and SRP effects. The cos(i) factor requires retrograde i > 90°, hence real SSO inclinations ~98°.

### Civil time is steered to Earth's rotation angle (UTC/UT1)
- **States:** UTC is adjusted by leap seconds "to ensure approximate agreement with UT1." |DUT1| ≤ 0.8 s; |UTC − UT1| ≤ 0.9 s; described as "a safeguard… against unpredictable changes in the rate of rotation of the Earth." IERS Bulletin C 72 (6 July 2026): UTC−TAI = −37 s since 2017-01-01; **no leap second at end of December 2026**.
- **Source:** ITU-R Rec. TF.460-6, Feb 2002; IERS Bulletin C 72, Observatoire de Paris.
- **Kind:** Specification plus operational record.
- **First-person checkable:** Yes, in part — receive a time signal (WWV, DCF77, MSF) and read the encoded DUT1; observe that clock noon and solar noon stay in step year over year.
- **Limits:** TF.460-6 superseded; the leap-second regime is scheduled to change by CGPM resolution. **This constrains Earth's rotation, not its shape or size** — it bears on the shape question only in establishing that a single global rotation angle underwrites all civil timekeeping.

### Coverage gaps declared by this compiler
- **Undersea cable routing:** only vendor communications available (e.g. Meta Engineering, Nov 2025, "2Africa's complete system length of 45,000 kilometers"). Whether that is a geodesic route length, cable-laid length including slack, or a marketing round number **is not stated by the source**. Omitted as an item.
- **Published flight times and great-circle distances:** in scope but unanchorable. Aggregators reported mutually inconsistent distances for the same route (11 017–11 083 km for JNB–SYD) and block times (11 h 15 m – 12 h 10 m) — "exactly the kind of disagreement I should not silently average." ICAO publishes no locatable route-distance table.
- Closed-form radar horizon distance not cleanly quotable from P.526 §3.2.
- FAA Order 8260.52, AC 90-101A (403); EUROCAE ED-75D, RTCA DO-236C (paywalled) — these state most explicitly that geodetic calculations must use the WGS-84 ellipsoid. Omitted rather than cited second-hand.
- ICAO Annex SARPs text itself paywalled/403.
- **Statements of what would fail if the assumption were wrong:** searched for specifically. **Standards bodies largely do not write them** — specifications state the model and tolerances, not the counterfactual. Closest found: IS-GPS-200 §20.3.3.4.3.2 (10⁸ m/semicircle sensitivity, why π is pinned to 14 digits) and ICAO Doc 9674 §1.1.3–1.1.4 (aircraft on different datums "could be seen… as having different positions"). **Both concern datum inconsistency, not a materially different Earth figure.**
- **Convention-dependence deliberately unresolved:** GPS user μ ≠ WGS 84 GM; "the radius of the Earth" has at least four tabulated values in NGA Table 3.5 alone (equatorial 6 378 137.0, polar 6 356 752.3142, mean-of-semi-axes 6 371 008.7714, equal-volume 6 371 000.7900 m) plus the ~8 500 km *effective* radius in ITU-R work, which is not a length at all but a refraction bookkeeping device. **No single figure selected.**
