$('.document_crm_name').on('change', function () {
    if ($(this).val().length > 0) {
        $('.group_document_crm_part').show()
    } else {
        $('.group_document_crm_part').find('button').each(function (key, value) {
            if($(this).attr('name') == 'delete') {
                $(this).click()
            }
        });
        $('.group_document_crm_part').hide()
    }
});