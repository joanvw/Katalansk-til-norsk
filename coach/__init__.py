"""coach – en coachende agent for opptak, forberedelse og analyse.

Formålet er å aktivere opptak (lyd/bilde) i ulike situasjoner, forberede
deg på hvem du møter og hvilke drivere de har, og gi tydelig, utviklende
tilbakemelding i etterkant – inkludert konkrete tips til dialogen med hver
enkelt ressurs i rommet. Personer kan huskes anonymisert i et profilarkiv,
slik at dere kan trene på håndteringen av relasjonene over tid.

Pakken er ren Python (standardbibliotek). Maskinvare- og
plattformavhengige deler – ekte lyd/bilde-opptak, skylagring og en
AI-analysator – kobles på via protokollene ``Opptaker``, ``Lagringsmål``
og ``Analysator``, på samme måte som ``dmx_spot_detect`` kobler på ekte
DMX-maskinvare.
"""

from .ai_analysis import (
    AIAnalysator,
    AnthropicKlient,
    KIKlient,
    STANDARD_MODELL,
)
from .analysis import Analysator, Observasjoner, RegelbasertAnalysator
from .coach import Coach
from .models import (
    CoachingØkt,
    Deltaker,
    DeltakerTilbakemelding,
    Forberedelse,
    Lagringssted,
    Møteoppsett,
    Opptak,
    Opptaksmodus,
    Opptaksstatus,
    Profil,
    Tilbakemelding,
)
from .preparation import forbered, kartlegg_drivere
from .profiles import ProfilArkiv, lag_profil_id
from .recorder import (
    Lagringsmål,
    LokalLagring,
    MinneLagring,
    MockOpptaker,
    Opptaker,
    Opptaksøkt,
)
from .situations import (
    Agenda,
    Driver,
    KJENTE_ROLLER,
    Møtested,
    Situasjon,
    ØnsketUtkomme,
)

__all__ = [
    "Coach",
    # situasjonsvalg
    "Situasjon",
    "Agenda",
    "Møtested",
    "ØnsketUtkomme",
    "Driver",
    "KJENTE_ROLLER",
    # modeller
    "Deltaker",
    "Møteoppsett",
    "Opptak",
    "Opptaksmodus",
    "Lagringssted",
    "Opptaksstatus",
    "Forberedelse",
    "Tilbakemelding",
    "DeltakerTilbakemelding",
    "CoachingØkt",
    "Profil",
    # forberedelse
    "forbered",
    "kartlegg_drivere",
    # opptak / lagring
    "Opptaker",
    "Lagringsmål",
    "Opptaksøkt",
    "MockOpptaker",
    "LokalLagring",
    "MinneLagring",
    # profiler
    "ProfilArkiv",
    "lag_profil_id",
    # analyse
    "Analysator",
    "RegelbasertAnalysator",
    "Observasjoner",
    # KI-analyse
    "AIAnalysator",
    "AnthropicKlient",
    "KIKlient",
    "STANDARD_MODELL",
]
