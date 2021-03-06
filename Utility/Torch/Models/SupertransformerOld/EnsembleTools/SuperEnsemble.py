from typing import List, Optional, Tuple

from torch import nn

from Utility.Torch.Models.SupertransformerOld import StreamTools
from Utility.Torch.Models.SupertransformerOld.StreamTools import StreamTensor

from Utility.Torch.Models.SupertransformerOld.EnsembleTools.ResStartup import AbstractResStartup
from Utility.Torch.Models.SupertransformerOld.EnsembleTools.Startup import AbstractEnsembleStartup
from Utility.Torch.Models.SupertransformerOld.EnsembleTools.SubModels import AbstractSubModel
from Utility.Torch.Models.SupertransformerOld.EnsembleTools.Teardown import AbstractPredictor


class ProcessingGrid(nn.Module):
    """
    Contains a collection of processing units, and
    starting values. Runs an update every time it
    is called.
    """

    def __init__(self, units: List[List[AbstractProcessingUnit]]):
        super().__init__()
        final_list: List[nn.ModuleList] = []
        for submodel in units:
            final_list.append(nn.ModuleList(submodel))
        self.module_grid = nn.ModuleList(final_list)
        self.linear_grid = [[None] * len(final_list[0]) for _ in final_list]
        self.orthogonal_grid = [[None] * len(final_list[0]) for _ in final_list]

    def forward(self,
                linear_input: List[Optional[torch.Tensor]],
                orthogonal_input: List[Optional[torch.Tensor]]):

        # Peform update propogation
        self.linear_grid.insert(0, linear_input)
        linear_output = self.linear_grid.pop()

        self.orthogonal_grid.insert(0, orthogonal_input)
        orthogonal_output = self.orthogonal_grid.pop()

        # Work through the grid
        for i, submodel in enumerate(self.module_grid):
            for j, unit in enumerate(submodel):
                linear = self.linear_grid[i][j]
                orthogonal = self.orthogonal_grid[j][i]
                if linear is not None and orthogonal is not None:
                    assert linear.batch == orthogonal.batch
                    assert linear.signals == orthogonal.signals
                    outcome = unit(linear, orthogonal, signals)
                    linear = outcome
                    orthogonal = outcome
                self.linear_grid[i][j] = linear
                self.orthogonal_grid[j][i] = orthogonal

        # Return the finished items
        return linear_output, orthogonal_output



class SuperEnsemble(nn.Module):
    """

    A SuperEnsemble model. Consists of a
    collection of residually active submodels, and memory starts.
    May generate only it's own memory starts, or accept augmentive
    information from prior models as well.
    """

    def __init__(self,
                 Start: List[AbstractEnsembleStartup],
                 ResStart: List[AbstractResStartup],
                 TearDown: List[AbstractPredictor],
                 SubModels: List[AbstractSubModel],
                 ):


        super().__init__()

        self.starters = Start
        self.res = ResStart
        self.teardown = TearDown
        self.submodels = SubModels

    def forward(self,
                input_stream: StreamTensor,
                residuals_stream: Optional[List[StreamTensor]],
                ensemble_streams: Optional[List[StreamTensor]],
                auxiliary_stream: Optional[StreamTensor])\
            -> Tuple[StreamTensor, List[StreamTensor], List[StreamTensor]]:

        """

        :param input_stream: The input to the model
        :param residuals_stream: Any prior residuals generated to incorporate
        :param ensemble_stream: Any prior per task information or conditioning to incoporate.
        :param auxiliary_stream: A place to put information that will be fed to each submodel.
        :return: A stream tensor, the output. A List of StreamTensors,
            one per submodel task recursive information. A list of StreamTensors, consisting
            of residual information.
        """
        #Strip out stream losses, metrics. Put them in null stream, to merge into the output later.
        null_stream = input_stream.keeponly([]) #Only keeps metrics, losses.
        input_stream = input_stream.branch(input_stream.names)

        #Preprocess, start tensors for ensemble
        if ensemble_streams is not None:
            iterate = zip(ensemble_streams, self.starters)
            stream = [start(input_stream, ensemble_stream, auxiliary_stream) for ensemble_stream, start in iterate]
        else:
            stream = [start(input_stream, None, auxiliary_stream) for start in self.starters]

        if residuals_stream is not None:
            iterate = zip(residuals_stream, self.res)
            residuals = [res_start(residual, auxiliary_stream) for residual, res_start in iterate]
        else:
            residuals = [res_start(None, auxiliary_stream) for res_start in self.res]

        #Perform submodel ensemble processing
        outputs: List[StreamTensor] = []
        for substream, submodel in zip(stream, self.submodels):
            output, residuals = submodel(substream, auxiliary_stream)
            outputs.append(output)

        #collapse the accumulated ensemble
        ensemble_items: List[StreamTensor] = []
        cumulative: Optional[StreamTensor] = None
        for output, final in zip(outputs, self.teardown):
            cumulative, ensemble_item = final(output, cumulative, auxiliary_stream)
            ensemble_items.append(ensemble_item)

        #Integrate metrics, losses back into stream.
        merging = StreamTools.StreamMerger([cumulative, null_stream])
        merging.losses.sum()
        merging.stream.sum()
        output = merging.build()

        #Return
        return output, residuals, ensemble_items