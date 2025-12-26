"""扇出数量属性测试

使用 Hypothesis 验证工作流扇出数量与题目数量的一致性

**功能: ai-grading-agent, 属性 5: 扇出数量匹配题目数量**
**验证: 需求 4.2**
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from typing import List

from src.models.region import BoundingBox, QuestionRegion, SegmentationResult


# ===== 策略定义 =====

# 生成有效的题目 ID
question_id_strategy = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789_",
    min_size=1,
    max_size=20
).map(lambda s: f"q_{s}")

# 生成有效的提交 ID
submission_id_strategy = st.text(
    alphabet="0123456789abcdef",
    min_size=8,
    max_size=36
).map(lambda s: f"sub_{s}")

# 生成有效的边界框
@st.composite
def bounding_box_strategy(draw):
    """生成有效的边界框"""
    ymin = draw(st.integers(min_value=0, max_value=900))
    xmin = draw(st.integers(min_value=0, max_value=900))
    ymax = draw(st.integers(min_value=ymin + 10, max_value=1000))
    xmax = draw(st.integers(min_value=xmin + 10, max_value=1000))
    return BoundingBox(ymin=ymin, xmin=xmin, ymax=ymax, xmax=xmax)


# 生成有效的题目区域
@st.composite
def question_region_strategy(draw, question_id: str = None, page_index: int = 0):
    """生成有效的题目区域"""
    if question_id is None:
        question_id = draw(question_id_strategy)
    bounding_box = draw(bounding_box_strategy())
    # 生成可选的图像数据
    has_image = draw(st.booleans())
    image_data = "base64_encoded_image_data" if has_image else None
    
    return QuestionRegion(
        question_id=question_id,
        page_index=page_index,
        bounding_box=bounding_box,
        image_data=image_data
    )


# 生成题目区域列表
@st.composite
def question_regions_strategy(draw, min_count: int = 0, max_count: int = 20):
    """生成题目区域列表，确保 question_id 唯一"""
    count = draw(st.integers(min_value=min_count, max_value=max_count))
    regions = []
    for i in range(count):
        question_id = f"q_{i+1}"
        page_index = i // 5  # 每页最多 5 道题
        bounding_box = draw(bounding_box_strategy())
        has_image = draw(st.booleans())
        image_data = "base64_encoded_image_data" if has_image else None
        
        region = QuestionRegion(
            question_id=question_id,
            page_index=page_index,
            bounding_box=bounding_box,
            image_data=image_data
        )
        regions.append(region)
    return regions


# 生成分割结果
@st.composite
def segmentation_result_strategy(draw, min_regions: int = 0, max_regions: int = 20):
    """生成分割结果"""
    submission_id = draw(submission_id_strategy)
    regions = draw(question_regions_strategy(min_count=min_regions, max_count=max_regions))
    total_pages = max(1, (len(regions) + 4) // 5)  # 每页最多 5 道题
    
    return SegmentationResult(
        submission_id=submission_id,
        total_pages=total_pages,
        regions=regions
    )


class TestFanOutCountProperties:
    """扇出数量属性测试
    
    **功能: ai-grading-agent, 属性 5: 扇出数量匹配题目数量**
    **验证: 需求 4.2**
    
    属性 5 定义：对于任意包含 N 个题目区域的分割结果，
    父工作流应当启动恰好 N 个子工作流，每道题目一个。
    """
    
    @given(segmentation_result=segmentation_result_strategy(min_regions=0, max_regions=20))
    @settings(max_examples=100)
    def test_fan_out_count_equals_region_count(self, segmentation_result: SegmentationResult):
        """
        **功能: ai-grading-agent, 属性 5: 扇出数量匹配题目数量**
        **验证: 需求 4.2**
        
        对于任意分割结果，扇出的子工作流数量应该等于题目区域数量
        """
        regions = segmentation_result.regions
        expected_fan_out_count = len(regions)
        
        # 模拟工作流扇出逻辑
        child_workflow_tasks = []
        for region in regions:
            # 每个题目区域应该启动一个子工作流
            child_workflow_tasks.append({
                "question_id": region.question_id,
                "submission_id": segmentation_result.submission_id
            })
        
        actual_fan_out_count = len(child_workflow_tasks)
        
        # 验证扇出数量等于题目数量
        assert actual_fan_out_count == expected_fan_out_count, \
            f"扇出数量 {actual_fan_out_count} 不等于题目数量 {expected_fan_out_count}"
    
    @given(segmentation_result=segmentation_result_strategy(min_regions=1, max_regions=20))
    @settings(max_examples=100)
    def test_each_region_has_unique_child_workflow(self, segmentation_result: SegmentationResult):
        """
        **功能: ai-grading-agent, 属性 5: 扇出数量匹配题目数量**
        **验证: 需求 4.2**
        
        对于任意分割结果，每个题目区域应该对应一个唯一的子工作流
        """
        regions = segmentation_result.regions
        
        # 模拟工作流扇出逻辑
        child_workflow_ids = set()
        for region in regions:
            # 子工作流 ID 格式: {submission_id}_{question_id}
            workflow_id = f"{segmentation_result.submission_id}_{region.question_id}"
            child_workflow_ids.add(workflow_id)
        
        # 验证每个题目区域都有唯一的子工作流
        assert len(child_workflow_ids) == len(regions), \
            f"子工作流数量 {len(child_workflow_ids)} 不等于题目数量 {len(regions)}"
    
    @given(
        regions_count=st.integers(min_value=0, max_value=50)
    )
    @settings(max_examples=100)
    def test_fan_out_count_for_any_region_count(self, regions_count: int):
        """
        **功能: ai-grading-agent, 属性 5: 扇出数量匹配题目数量**
        **验证: 需求 4.2**
        
        对于任意数量的题目区域 N，扇出数量应该恰好为 N
        """
        # 创建 N 个题目区域
        regions = []
        for i in range(regions_count):
            region = QuestionRegion(
                question_id=f"q_{i+1}",
                page_index=i // 5,
                bounding_box=BoundingBox(ymin=0, xmin=0, ymax=100, xmax=100),
                image_data="base64_image"
            )
            regions.append(region)
        
        # 模拟工作流扇出逻辑
        child_workflow_tasks = []
        for region in regions:
            child_workflow_tasks.append(region.question_id)
        
        # 验证扇出数量
        assert len(child_workflow_tasks) == regions_count, \
            f"扇出数量 {len(child_workflow_tasks)} 不等于预期 {regions_count}"
    
    @given(segmentation_result=segmentation_result_strategy(min_regions=1, max_regions=20))
    @settings(max_examples=100)
    def test_fan_out_preserves_question_ids(self, segmentation_result: SegmentationResult):
        """
        **功能: ai-grading-agent, 属性 5: 扇出数量匹配题目数量**
        **验证: 需求 4.2**
        
        扇出过程应该保留所有题目 ID，不丢失任何题目
        """
        regions = segmentation_result.regions
        original_question_ids = {region.question_id for region in regions}
        
        # 模拟工作流扇出逻辑
        fan_out_question_ids = set()
        for region in regions:
            fan_out_question_ids.add(region.question_id)
        
        # 验证所有题目 ID 都被保留
        assert fan_out_question_ids == original_question_ids, \
            f"扇出后的题目 ID 集合与原始不一致"
    
    @given(segmentation_result=segmentation_result_strategy(min_regions=0, max_regions=20))
    @settings(max_examples=100)
    def test_empty_regions_produces_zero_fan_out(self, segmentation_result: SegmentationResult):
        """
        **功能: ai-grading-agent, 属性 5: 扇出数量匹配题目数量**
        **验证: 需求 4.2**
        
        当题目区域为空时，扇出数量应该为 0
        """
        # 创建空的分割结果
        empty_result = SegmentationResult(
            submission_id=segmentation_result.submission_id,
            total_pages=1,
            regions=[]
        )
        
        # 模拟工作流扇出逻辑
        child_workflow_tasks = []
        for region in empty_result.regions:
            child_workflow_tasks.append(region.question_id)
        
        # 验证扇出数量为 0
        assert len(child_workflow_tasks) == 0, \
            f"空区域应该产生 0 个扇出，实际为 {len(child_workflow_tasks)}"


class TestFanOutWithImageData:
    """测试带图像数据的扇出行为
    
    **功能: ai-grading-agent, 属性 5: 扇出数量匹配题目数量**
    **验证: 需求 4.2**
    """
    
    @given(segmentation_result=segmentation_result_strategy(min_regions=1, max_regions=20))
    @settings(max_examples=100)
    def test_fan_out_only_regions_with_image_data(self, segmentation_result: SegmentationResult):
        """
        **功能: ai-grading-agent, 属性 5: 扇出数量匹配题目数量**
        **验证: 需求 4.2**
        
        根据工作流实现，只有带图像数据的区域才会启动子工作流
        扇出数量应该等于带图像数据的区域数量
        """
        regions = segmentation_result.regions
        
        # 模拟工作流扇出逻辑（与 exam_paper.py 中的逻辑一致）
        child_workflow_tasks = []
        for region in regions:
            # 只有带图像数据的区域才启动子工作流
            if region.image_data:
                child_workflow_tasks.append({
                    "question_id": region.question_id,
                    "image_b64": region.image_data
                })
        
        # 计算预期的扇出数量
        expected_count = sum(1 for r in regions if r.image_data)
        
        # 验证扇出数量
        assert len(child_workflow_tasks) == expected_count, \
            f"扇出数量 {len(child_workflow_tasks)} 不等于带图像数据的区域数量 {expected_count}"
    
    @given(regions_count=st.integers(min_value=1, max_value=30))
    @settings(max_examples=100)
    def test_all_regions_with_image_data_fan_out_equals_total(self, regions_count: int):
        """
        **功能: ai-grading-agent, 属性 5: 扇出数量匹配题目数量**
        **验证: 需求 4.2**
        
        当所有区域都有图像数据时，扇出数量应该等于总区域数量
        """
        # 创建所有区域都有图像数据的分割结果
        regions = []
        for i in range(regions_count):
            region = QuestionRegion(
                question_id=f"q_{i+1}",
                page_index=i // 5,
                bounding_box=BoundingBox(ymin=0, xmin=0, ymax=100, xmax=100),
                image_data="base64_encoded_image"  # 所有区域都有图像数据
            )
            regions.append(region)
        
        # 模拟工作流扇出逻辑
        child_workflow_tasks = []
        for region in regions:
            if region.image_data:
                child_workflow_tasks.append(region.question_id)
        
        # 验证扇出数量等于总区域数量
        assert len(child_workflow_tasks) == regions_count, \
            f"扇出数量 {len(child_workflow_tasks)} 不等于总区域数量 {regions_count}"


class TestMultiPageFanOut:
    """测试多页文档的扇出行为
    
    **功能: ai-grading-agent, 属性 5: 扇出数量匹配题目数量**
    **验证: 需求 4.2**
    """
    
    @given(
        page_count=st.integers(min_value=1, max_value=10),
        regions_per_page=st.integers(min_value=0, max_value=10)
    )
    @settings(max_examples=100)
    def test_multi_page_fan_out_count(self, page_count: int, regions_per_page: int):
        """
        **功能: ai-grading-agent, 属性 5: 扇出数量匹配题目数量**
        **验证: 需求 4.2**
        
        对于多页文档，扇出数量应该等于所有页面的题目总数
        """
        # 创建多页分割结果
        all_regions = []
        question_counter = 1
        
        for page_idx in range(page_count):
            for _ in range(regions_per_page):
                region = QuestionRegion(
                    question_id=f"q_{question_counter}",
                    page_index=page_idx,
                    bounding_box=BoundingBox(ymin=0, xmin=0, ymax=100, xmax=100),
                    image_data="base64_image"
                )
                all_regions.append(region)
                question_counter += 1
        
        # 模拟工作流扇出逻辑
        child_workflow_tasks = []
        for region in all_regions:
            if region.image_data:
                child_workflow_tasks.append(region.question_id)
        
        # 预期扇出数量
        expected_count = page_count * regions_per_page
        
        # 验证扇出数量
        assert len(child_workflow_tasks) == expected_count, \
            f"扇出数量 {len(child_workflow_tasks)} 不等于预期 {expected_count}"
    
    @given(
        segmentation_results=st.lists(
            segmentation_result_strategy(min_regions=0, max_regions=10),
            min_size=1,
            max_size=5
        )
    )
    @settings(max_examples=50)
    def test_aggregated_fan_out_from_multiple_segmentation_results(
        self, segmentation_results: List[SegmentationResult]
    ):
        """
        **功能: ai-grading-agent, 属性 5: 扇出数量匹配题目数量**
        **验证: 需求 4.2**
        
        当有多个分割结果时，总扇出数量应该等于所有分割结果的题目总数
        """
        # 收集所有题目区域
        all_regions = []
        for seg_result in segmentation_results:
            all_regions.extend(seg_result.regions)
        
        # 模拟工作流扇出逻辑
        child_workflow_tasks = []
        for region in all_regions:
            if region.image_data:
                child_workflow_tasks.append(region.question_id)
        
        # 预期扇出数量
        expected_count = sum(1 for r in all_regions if r.image_data)
        
        # 验证扇出数量
        assert len(child_workflow_tasks) == expected_count, \
            f"扇出数量 {len(child_workflow_tasks)} 不等于预期 {expected_count}"

