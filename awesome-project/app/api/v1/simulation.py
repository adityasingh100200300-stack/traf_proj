from fastapi import APIRouter, status
from app.simulation.controller import SimulationController
from app.schemas.simulation import SimulationStepResponse, SimulationStatusResponse
from app.core.config import settings

router = APIRouter()

@router.get(
    "/simulation/status",
    response_model=SimulationStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get simulation engine status"
)
async def get_simulation_status():
    client = SimulationController.get_client()
    return SimulationStatusResponse(
        connected=await client.is_connected(),
        mode=settings.SIMULATION_MODE
    )

@router.post(
    "/simulation/step",
    response_model=SimulationStepResponse,
    status_code=status.HTTP_200_OK,
    summary="Step digital twin simulation",
    description="Advances the digital twin simulation by one step, runs adaptive signal optimization, and synchronizes signal phase timings."
)
async def step_simulation(intersection_id: str = "INT-001"):
    return await SimulationController.step_and_sync(intersection_id=intersection_id)